@echo off
chcp 65001 >nul
title SmartVideoClipper - 智能视频解说生成器

echo ==========================================
echo    SmartVideoClipper - 智能视频解说生成器
echo    比NarratoAI更智能、比FunClip更自动
echo ==========================================
echo.

:: 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ 未找到虚拟环境，请先运行 install_all.bat
    pause
    exit /b 1
)

:: 检查Ollama是否运行
echo [检查] Ollama服务状态...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ Ollama服务未运行，正在启动...
    start "" ollama serve
    timeout /t 3 /nobreak >nul
)

:: 启动Gradio界面
echo.
echo 🚀 正在启动Web界面...
echo 请在浏览器中打开: http://localhost:7860
echo.
echo 按 Ctrl+C 可以停止服务
echo ==========================================
echo.

python app/gradio_ui.py

pause

