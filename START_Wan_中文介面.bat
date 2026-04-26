@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$portOpen = (Test-NetConnection 127.0.0.1 -Port 8188 -InformationLevel Quiet); ^
   if (-not $portOpen) { ^
     Start-Process -FilePath (Join-Path $PWD 'ComfyUI_windows_portable\python_embeded\python.exe') -ArgumentList '-s','ComfyUI\main.py','--windows-standalone-build','--lowvram','--disable-cuda-malloc','--disable-auto-launch' -WorkingDirectory (Join-Path $PWD 'ComfyUI_windows_portable') -WindowStyle Hidden; ^
     Start-Sleep -Seconds 8; ^
   }; ^
   $uiOpen = (Test-NetConnection 127.0.0.1 -Port 7860 -InformationLevel Quiet); ^
   if (-not $uiOpen) { ^
     Start-Process -FilePath (Join-Path $PWD 'ComfyUI_windows_portable\python_embeded\python.exe') -ArgumentList 'wan_local_ui\server.py' -WorkingDirectory $PWD -WindowStyle Hidden; ^
   }; ^
   Start-Sleep -Seconds 2; ^
   Start-Process 'http://127.0.0.1:7860'"

endlocal
