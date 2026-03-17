@echo off
echo Starting GGD-AI Development Server...

:: 启动Python后端
echo Starting Python backend...
start "Python Backend" cmd /k "conda run -n python3.12 python src/main.py"

:: 等待Python启动
timeout /t 3

:: 启动Tauri前端
echo Starting Tauri frontend...
npm run tauri:dev
