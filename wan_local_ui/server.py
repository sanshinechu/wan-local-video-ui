from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request, parse
import json
import mimetypes
import os
import random
import re
import time
import uuid


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
UPLOAD_DIR = ROOT / "uploads"
COMFY_INPUT_DIR = PROJECT / "ComfyUI_windows_portable" / "ComfyUI" / "input"
COMFY = "http://127.0.0.1:8188"
HOST = "127.0.0.1"
PORT = 7860


UPLOAD_DIR.mkdir(exist_ok=True)
COMFY_INPUT_DIR.mkdir(exist_ok=True)


RESOLUTIONS = {
    "480p": {
        "16:9": (832, 480),
        "9:16": (480, 832),
        "1:1": (640, 640),
        "4:3": (704, 528),
        "3:4": (528, 704),
    },
    "360p": {
        "16:9": (640, 368),
        "9:16": (368, 640),
        "1:1": (512, 512),
        "4:3": (576, 432),
        "3:4": (432, 576),
    },
    "低顯存測試": {
        "16:9": (512, 288),
        "9:16": (288, 512),
        "1:1": (384, 384),
        "4:3": (448, 336),
        "3:4": (336, 448),
    },
}


def api_json(path, payload=None, timeout=30):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(f"{COMFY}{path}", data=data, headers=headers)
    with request.urlopen(req, timeout=timeout) as res:
        body = res.read()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))


def frames_from_seconds(seconds, fps):
    frames = int(seconds * fps) + 1
    remainder = (frames - 1) % 4
    if remainder:
        frames += 4 - remainder
    return max(5, frames)


def clean_prefix(text):
    text = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", text.strip())[:28]
    return text or "video"


def build_prompt(data):
    mode = data.get("mode", "t2v")
    ratio = data.get("ratio", "16:9")
    resolution = data.get("resolution", "低顯存測試")
    width, height = RESOLUTIONS.get(resolution, RESOLUTIONS["低顯存測試"]).get(ratio, (512, 288))
    seconds = int(data.get("seconds", 3))
    fps = int(data.get("fps", 8))
    steps = int(data.get("steps", 18))
    cfg = float(data.get("cfg", 6.0))
    seed = int(data.get("seed") or random.randrange(1, 2**32 - 1))
    positive = data.get("prompt", "").strip()
    negative = data.get("negative", "").strip() or "low quality, blurry, distorted, watermark, text"
    frames = frames_from_seconds(seconds, fps)
    prefix = f"WanLocal/{time.strftime('%Y%m%d_%H%M%S')}_{clean_prefix(positive)}"

    if mode == "i2v":
        image_name = data.get("image")
        if not image_name:
            raise ValueError("圖片轉影片需要先上傳參考圖片。")
        prompt = {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": "wan2.1-i2v-14b-480p-Q3_K_S.gguf"},
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "cpu",
                },
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
            },
            "4": {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["1", 0], "shift": 3.0},
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": positive},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": negative},
            },
            "7": {
                "class_type": "LoadImage",
                "inputs": {"image": image_name},
            },
            "8": {
                "class_type": "CLIPVisionLoader",
                "inputs": {"clip_name": "clip_vision_h.safetensors"},
            },
            "9": {
                "class_type": "CLIPVisionEncode",
                "inputs": {"clip_vision": ["8", 0], "image": ["7", 0], "crop": "center"},
            },
            "10": {
                "class_type": "WanImageToVideo",
                "inputs": {
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "vae": ["3", 0],
                    "width": width,
                    "height": height,
                    "length": frames,
                    "batch_size": 1,
                    "clip_vision_output": ["9", 0],
                    "start_image": ["7", 0],
                },
            },
            "11": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "uni_pc",
                    "scheduler": "simple",
                    "positive": ["10", 0],
                    "negative": ["10", 1],
                    "latent_image": ["10", 2],
                    "denoise": 1.0,
                },
            },
            "12": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["11", 0], "vae": ["3", 0]},
            },
            "13": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["12", 0], "fps": fps},
            },
            "14": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["13", 0],
                    "filename_prefix": prefix.replace("WanLocal/", "WanLocal/I2V_"),
                    "format": "mp4",
                    "codec": "h264",
                },
            },
        }
        return {
            "client_id": str(uuid.uuid4()),
            "prompt": prompt,
            "meta": {
                "mode": "圖片轉影片",
                "width": width,
                "height": height,
                "frames": frames,
                "fps": fps,
                "seed": seed,
                "reference_image": image_name,
                "audio_note": "Wan 2.1 I2V 14B GGUF 本機模型不會產生音訊。",
            },
        }

    return {
        "client_id": str(uuid.uuid4()),
        "prompt": {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "wan2.1_t2v_1.3B_fp16.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "cpu",
                },
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
            },
            "4": {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["1", 0], "shift": 8.0},
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": positive},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": negative},
            },
            "7": {
                "class_type": "EmptyHunyuanLatentVideo",
                "inputs": {
                    "width": width,
                    "height": height,
                    "length": frames,
                    "batch_size": 1,
                },
            },
            "8": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "uni_pc",
                    "scheduler": "simple",
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": ["7", 0],
                    "denoise": 1.0,
                },
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
            },
            "10": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["9", 0], "fps": fps},
            },
            "11": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["10", 0],
                    "filename_prefix": prefix,
                    "format": "mp4",
                    "codec": "h264",
                },
            },
        },
        "meta": {
            "mode": "文字轉影片",
            "width": width,
            "height": height,
            "frames": frames,
            "fps": fps,
            "seed": seed,
            "audio_note": "Wan 2.1 T2V 1.3B 本機模型不會產生音訊。",
        },
    }


def find_outputs(history):
    outputs = []
    for node in history.get("outputs", {}).values():
        for item in node.get("videos", []) + node.get("images", []):
            filename = item.get("filename")
            if filename:
                qs = parse.urlencode({
                    "filename": filename,
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                outputs.append({
                    "filename": filename,
                    "url": f"{COMFY}/view?{qs}",
                })
    return outputs


INDEX_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wan 2.1 本機影片生成</title>
  <style>
    :root { color-scheme: light; --ink:#1e293b; --muted:#64748b; --line:#d6dde8; --panel:#f7f9fc; --brand:#0f766e; --accent:#b45309; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; color: var(--ink); background: #eef2f7; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { display:flex; align-items:end; justify-content:space-between; gap:16px; margin-bottom:18px; }
    h1 { font-size: 28px; margin: 0 0 4px; letter-spacing: 0; }
    .sub { color: var(--muted); font-size: 14px; }
    .status { padding: 8px 12px; border:1px solid var(--line); border-radius:8px; background:white; font-size:14px; white-space:nowrap; }
    .grid { display:grid; grid-template-columns: 1.08fr .92fr; gap:16px; align-items:start; }
    section { background:white; border:1px solid var(--line); border-radius:8px; padding:16px; }
    label { display:block; font-weight:700; margin-bottom:7px; }
    textarea, input, select { width:100%; border:1px solid var(--line); border-radius:6px; padding:10px 11px; font: inherit; background:white; }
    textarea { min-height:150px; resize:vertical; line-height:1.55; }
    .row { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; margin-top:12px; }
    .row.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .hint { color: var(--muted); font-size:13px; margin-top:6px; line-height:1.45; }
    .drop { border:1px dashed #94a3b8; border-radius:8px; padding:18px; background:var(--panel); text-align:center; }
    .drop input { border:0; padding:0; margin-top:10px; }
    .switch { display:flex; align-items:center; gap:10px; margin-top:12px; }
    .switch input { width:18px; height:18px; }
    button { border:0; border-radius:7px; padding:11px 14px; font:inherit; font-weight:700; cursor:pointer; }
    .primary { width:100%; margin-top:16px; background:var(--brand); color:white; }
    .secondary { background:#e2e8f0; color:#0f172a; }
    button:disabled { opacity:.6; cursor:not-allowed; }
    .progress { height:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin:14px 0 8px; }
    .bar { height:100%; width:0%; background:var(--brand); transition:width .3s; }
    .log { min-height:88px; border:1px solid var(--line); border-radius:6px; background:#fbfdff; padding:10px; color:#334155; font-size:14px; line-height:1.5; white-space:pre-wrap; }
    video { width:100%; border-radius:8px; background:#111827; margin-top:12px; }
    .pill { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); border-radius:999px; padding:5px 9px; color:#475569; background:#fff; font-size:13px; margin:4px 6px 0 0; }
    .warn { color: var(--accent); }
    @media (max-width: 860px) { main { padding:16px; } .grid, .row, .row.three { grid-template-columns:1fr; } header { align-items:start; flex-direction:column; } .status { white-space:normal; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Wan 2.1 本機影片生成</h1>
      <div class="sub">使用本機 ComfyUI + Wan 2.1 T2V 1.3B，影片會存在 ComfyUI 的 output 資料夾。</div>
    </div>
    <div class="status" id="status">檢查 ComfyUI 中...</div>
  </header>

  <div class="grid">
    <section>
      <label for="prompt">提示詞</label>
      <textarea id="prompt" placeholder="例如：A warm classroom in Taiwan, students learning Scratch animation, soft morning light, cinematic, smooth camera movement"></textarea>
      <div class="hint">建議先用英文提示詞，Wan 影片模型通常會比較穩。</div>

      <div class="row">
        <div>
          <label for="mode">生成模式</label>
          <select id="mode">
            <option value="t2v" selected>文字轉影片</option>
            <option value="i2v">圖片轉影片</option>
          </select>
        </div>
        <div>
          <label>目前圖片</label>
          <div class="status" id="currentImage" style="white-space:normal">尚未上傳</div>
        </div>
      </div>

      <div class="row">
        <div>
          <label for="negative">反向提示詞</label>
          <input id="negative" value="low quality, blurry, distorted, watermark, text">
        </div>
        <div>
          <label for="seed">Seed</label>
          <input id="seed" type="number" placeholder="留空會自動產生">
        </div>
      </div>

      <div class="row three">
        <div>
          <label for="ratio">比例</label>
          <select id="ratio">
            <option>16:9</option>
            <option>9:16</option>
            <option>1:1</option>
            <option>4:3</option>
            <option>3:4</option>
          </select>
        </div>
        <div>
          <label for="resolution">解析度</label>
          <select id="resolution">
            <option selected>低顯存測試</option>
            <option>360p</option>
            <option>480p</option>
          </select>
        </div>
        <div>
          <label for="seconds">秒數</label>
          <select id="seconds">
            <option value="2">2 秒</option>
            <option value="3" selected>3 秒</option>
            <option value="4">4 秒</option>
            <option value="5">5 秒</option>
          </select>
        </div>
      </div>

      <div class="row three">
        <div>
          <label for="fps">FPS</label>
          <select id="fps">
            <option value="8" selected>8</option>
            <option value="12">12</option>
            <option value="16">16</option>
          </select>
        </div>
        <div>
          <label for="steps">品質步數</label>
          <select id="steps">
            <option value="12">快速 12</option>
            <option value="18" selected>標準 18</option>
            <option value="24">較細 24</option>
          </select>
        </div>
        <div>
          <label for="cfg">提示詞強度</label>
          <input id="cfg" type="number" min="1" max="12" step="0.5" value="6">
        </div>
      </div>

      <div class="switch">
        <input id="audio" type="checkbox">
        <label for="audio" style="margin:0">產生聲音</label>
      </div>
      <div class="hint warn">目前 Wan 2.1 T2V 1.3B 本機模型只產生無聲影片；這個選項先保留給之後接音訊模型。</div>

      <button class="primary" id="generate">生成影片</button>
    </section>

    <section>
      <label>參考圖片</label>
      <div class="drop">
        <div>圖片轉影片模式會使用這張圖當第一幀參考。</div>
        <input id="image" type="file" accept="image/*">
        <div id="uploadResult" class="hint"></div>
      </div>

      <div class="progress"><div class="bar" id="bar"></div></div>
      <div class="log" id="log">等待輸入提示詞。</div>
      <div id="meta"></div>
      <div id="result"></div>
    </section>
  </div>
</main>

<script>
const $ = (id) => document.getElementById(id);
let polling = null;
let referenceImage = "";

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "操作失敗");
  return data;
}

function setLog(text) { $("log").textContent = text; }
function setBar(percent) { $("bar").style.width = `${percent}%`; }

async function checkStatus() {
  try {
    const data = await api("/api/status");
    $("status").textContent = data.ok ? "ComfyUI 已連線" : "ComfyUI 尚未啟動";
  } catch {
    $("status").textContent = "ComfyUI 尚未啟動";
  }
}

$("image").addEventListener("change", async () => {
  const file = $("image").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("image", file);
  try {
    const data = await api("/api/upload", { method: "POST", body: form });
    referenceImage = data.filename;
    $("uploadResult").textContent = `已保存：${data.filename}`;
    $("currentImage").textContent = data.filename;
  } catch (err) {
    $("uploadResult").textContent = err.message;
  }
});

$("generate").addEventListener("click", async () => {
  const prompt = $("prompt").value.trim();
  if (!prompt) {
    setLog("請先輸入提示詞。");
    return;
  }
  if ($("mode").value === "i2v" && !referenceImage) {
    setLog("圖片轉影片需要先上傳參考圖片。");
    return;
  }
  $("generate").disabled = true;
  $("result").innerHTML = "";
  $("meta").innerHTML = "";
  setBar(8);
  setLog("送出生成工作中...");
  try {
    const payload = {
      mode: $("mode").value,
      prompt,
      negative: $("negative").value,
      ratio: $("ratio").value,
      resolution: $("resolution").value,
      seconds: $("seconds").value,
      fps: $("fps").value,
      steps: $("steps").value,
      cfg: $("cfg").value,
      seed: $("seed").value,
      audio: $("audio").checked,
      image: referenceImage
    };
    const data = await api("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    $("meta").innerHTML = `
      <span class="pill">${data.meta.mode}</span>
      <span class="pill">${data.meta.width} x ${data.meta.height}</span>
      <span class="pill">${data.meta.frames} frames</span>
      <span class="pill">${data.meta.fps} FPS</span>
      <span class="pill">Seed ${data.meta.seed}</span>`;
    setLog("已送到 ComfyUI 排隊。生成影片會花幾分鐘，請保持這個頁面開著。");
    poll(data.prompt_id, 15);
  } catch (err) {
    setBar(0);
    setLog(err.message);
    $("generate").disabled = false;
  }
});

async function poll(promptId, progress) {
  clearTimeout(polling);
  try {
    const data = await api(`/api/job/${promptId}`);
    if (data.done) {
      setBar(100);
      setLog("影片生成完成。");
      const videos = data.outputs.map(item => `
        <a class="pill" href="${item.url}" target="_blank" rel="noreferrer">開啟 ${item.filename}</a>
        <video controls src="${item.url}"></video>`).join("");
      $("result").innerHTML = videos || "<div class='hint'>已完成，但沒有找到影片輸出。</div>";
      $("generate").disabled = false;
      return;
    }
    const next = Math.min(progress + 4, 92);
    setBar(next);
    setLog(data.status || "生成中...");
    polling = setTimeout(() => poll(promptId, next), 5000);
  } catch (err) {
    setLog(err.message);
    $("generate").disabled = false;
  }
}

checkStatus();
setInterval(checkStatus, 10000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = parse.urlparse(self.path)
        if parsed.path == "/":
            data = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/api/status":
            try:
                api_json("/system_stats", timeout=5)
                self.send_json(200, {"ok": True})
            except Exception as exc:
                self.send_json(200, {"ok": False, "error": str(exc)})
            return
        if parsed.path.startswith("/api/job/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = api_json(f"/history/{parse.quote(prompt_id)}", timeout=10)
                item = history.get(prompt_id)
                if item:
                    self.send_json(200, {"done": True, "outputs": find_outputs(item)})
                else:
                    queue = api_json("/queue", timeout=10)
                    running = any(row[1] == prompt_id for row in queue.get("queue_running", []))
                    pending = any(row[1] == prompt_id for row in queue.get("queue_pending", []))
                    status = "ComfyUI 正在生成中..." if running else "工作仍在排隊中..." if pending else "等待 ComfyUI 回報..."
                    self.send_json(200, {"done": False, "status": status})
            except Exception as exc:
                self.send_json(500, {"error": f"查詢工作失敗：{exc}"})
            return
        self.send_error(404)

    def do_POST(self):
        parsed = parse.urlparse(self.path)
        if parsed.path == "/api/generate":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8"))
                workflow = build_prompt(data)
                res = api_json("/prompt", workflow, timeout=30)
                self.send_json(200, {"prompt_id": res["prompt_id"], "meta": workflow["meta"]})
            except Exception as exc:
                self.send_json(500, {"error": f"送出生成失敗：{exc}"})
            return
        if parsed.path == "/api/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                boundary = ctype.split("boundary=", 1)[1].encode()
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                parts = body.split(b"--" + boundary)
                saved = None
                for part in parts:
                    if b'name="image"' not in part or b"\r\n\r\n" not in part:
                        continue
                    header, content = part.split(b"\r\n\r\n", 1)
                    content = content.rsplit(b"\r\n", 1)[0]
                    match = re.search(rb'filename="([^"]+)"', header)
                    original = match.group(1).decode("utf-8", "ignore") if match else "reference.png"
                    suffix = Path(original).suffix.lower() or ".png"
                    filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
                    (UPLOAD_DIR / filename).write_bytes(content)
                    (COMFY_INPUT_DIR / filename).write_bytes(content)
                    saved = filename
                    break
                if not saved:
                    raise ValueError("沒有收到圖片檔。")
                self.send_json(200, {"filename": saved})
            except Exception as exc:
                self.send_json(500, {"error": f"上傳失敗：{exc}"})
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    os.chdir(PROJECT)
    print(f"Wan local UI: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
