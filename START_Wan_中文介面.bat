@echo off
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0"
set "PY=%ROOT%ComfyUI_windows_portable\python_embeded\python.exe"
set "COMFY_DIR=%ROOT%ComfyUI_windows_portable"
set "LOG_DIR=%ROOT%logs"

if not exist "%PY%" (
  echo Cannot find Python:
  echo %PY%
  pause
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Checking ComfyUI on http://127.0.0.1:8188 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-NetConnection 127.0.0.1 -Port 8188 -InformationLevel Quiet) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo Starting ComfyUI. This can take a few minutes on first launch.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY%' -ArgumentList '-s','ComfyUI\main.py','--windows-standalone-build','--lowvram','--disable-cuda-malloc','--disable-auto-launch','--log-stdout' -WorkingDirectory '%COMFY_DIR%' -WindowStyle Hidden -RedirectStandardOutput '%LOG_DIR%\comfyui_launcher_stdout.log' -RedirectStandardError '%LOG_DIR%\comfyui_launcher_stderr.log'"
)

echo Waiting for ComfyUI ...
set "COMFY_READY=0"
for /L %%i in (1,1,60) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-NetConnection 127.0.0.1 -Port 8188 -InformationLevel Quiet) { exit 0 } else { exit 1 }"
  if not errorlevel 1 (
    set "COMFY_READY=1"
    goto comfy_done
  )
  timeout /t 5 /nobreak >nul
)

:comfy_done
if not "%COMFY_READY%"=="1" (
  echo ComfyUI did not start in time.
  echo Check logs:
  echo %LOG_DIR%\comfyui_launcher_stdout.log
  echo %LOG_DIR%\comfyui_launcher_stderr.log
  pause
  exit /b 1
)

echo Checking Wan local UI on http://127.0.0.1:7860 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-NetConnection 127.0.0.1 -Port 7860 -InformationLevel Quiet) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo Starting Wan local UI.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PY%' -ArgumentList 'wan_local_ui\server.py' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%LOG_DIR%\wan_ui_launcher_stdout.log' -RedirectStandardError '%LOG_DIR%\wan_ui_launcher_stderr.log'"
  timeout /t 2 /nobreak >nul
)

echo Opening browser ...
start "" "http://127.0.0.1:7860"
echo.
echo Ready. You can close this window after the browser opens.
pause

endlocal
