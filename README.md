# Wan 2.1 本機影片生成中文介面

這個專案是給 Windows 本機 ComfyUI 使用的繁體中文操作介面，目標是讓使用者用瀏覽器產生 Wan 2.1 影片，不必直接操作 ComfyUI 節點。

## 功能

- 文字轉影片：Wan 2.1 T2V 1.3B
- 圖片轉影片：Wan 2.1 I2V 14B 480P GGUF Q3_K_S
- 繁體中文網頁介面
- 可調整比例、解析度、秒數、FPS、品質步數、提示詞強度
- 支援上傳參考圖片
- 影片輸出到 ComfyUI 的 `output` 資料夾

## 本機需求

- Windows
- NVIDIA GPU，建議至少 8GB VRAM
- 已安裝 ComfyUI Windows portable
- 已安裝 ComfyUI-GGUF custom node
- 已下載 Wan 2.1 T2V / I2V 相關模型

## 已排除在 GitHub 外的內容

以下內容不會上傳到 GitHub：

- `ComfyUI_windows_portable/`
- `downloads/`
- `logs/`
- Wan 2.1 模型檔
- 產生的影片
- 使用者上傳的圖片

這些檔案很大，應該留在本機。

## 啟動方式

在本機雙擊：

```bat
START_Wan_中文介面.bat
```

瀏覽器會開啟：

```text
http://127.0.0.1:7860
```

ComfyUI 原生介面在：

```text
http://127.0.0.1:8188
```

## 建議測試設定

RTX 4060 8GB 建議先用：

- 解析度：低顯存測試
- 秒數：2 秒
- FPS：8
- 品質步數：12

I2V 是 14B 模型，即使用 GGUF Q3_K_S 低顯存版，仍然會很慢。
