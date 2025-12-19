@echo off
chcp 65001 >nul
title SmartVideoClipper - 一键安装脚本

echo ==========================================
echo   SmartVideoClipper v4.0 - 一键安装脚本
echo   比NarratoAI更强大的开源方案
echo ==========================================
echo.

:: 检查Python版本
echo [检查] Python版本...
python --version 2>nul
if %errorlevel% neq 0 (
    echo ❌ 错误: 未找到Python！请先安装Python 3.10+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 0. 配置国内镜像源（重要！）
echo.
echo [0/10] 配置国内pip镜像源...
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

:: 1. 创建虚拟环境
echo [1/10] 创建Python虚拟环境...
if exist venv (
    echo    虚拟环境已存在，跳过创建
) else (
    python -m venv venv
)
call venv\Scripts\activate.bat

:: 2. 配置Hugging Face国内镜像（模型下载用）
echo [2/10] 配置HuggingFace国内镜像...
set HF_ENDPOINT=https://hf-mirror.com
setx HF_ENDPOINT https://hf-mirror.com >nul 2>&1

:: 3. 升级pip
echo [3/10] 升级pip...
python -m pip install --upgrade pip -q

:: 4. 安装PyTorch（GPU版本）
echo [4/10] 安装PyTorch (GPU版本)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
if %errorlevel% neq 0 (
    echo    ⚠️ GPU版本安装失败，尝试CPU版本...
    pip install torch torchvision torchaudio -q
)

:: 5. 安装基础依赖
echo [5/10] 安装基础依赖...
pip install numpy opencv-python pillow tqdm python-dotenv httpx beautifulsoup4 lxml aiofiles ollama -q

:: 6. 安装镜头检测
echo [6/10] 安装PySceneDetect (镜头切分)...
pip install "scenedetect[opencv]" -q

:: 7. 安装Auto-Editor
echo [7/10] 安装Auto-Editor (静音剪除)...
pip install auto-editor -q

:: 8. 安装语音识别
echo [8/10] 安装faster-whisper (语音识别)...
pip install faster-whisper -q

:: 9. 安装Chinese-CLIP
echo [9/10] 安装Chinese-CLIP (画面分析-国内版)...
pip install cn-clip -q
if %errorlevel% neq 0 (
    echo    ⚠️ cn-clip安装失败，尝试从GitHub安装...
    pip install git+https://github.com/OFA-Sys/Chinese-CLIP.git -q
)

:: 10. 安装TTS和视频处理
echo [10/10] 安装TTS和视频处理库...
pip install edge-tts moviepy pydub gradio -q
echo    尝试安装ChatTTS (可能失败，Edge-TTS作为备选)...
pip install git+https://github.com/2noise/ChatTTS.git -q 2>nul
if %errorlevel% neq 0 (
    echo    ⚠️ ChatTTS安装失败，将使用Edge-TTS（效果也很好！）
)

echo.
echo ==========================================
echo   ✅ Python依赖安装完成！
echo ==========================================
echo.
echo 🔧 还需要手动安装以下工具：
echo.
echo 1. FFmpeg (必需):
echo    下载: https://www.gyan.dev/ffmpeg/builds/
echo    下载 ffmpeg-release-essentials.zip
echo    解压后将 bin 目录添加到系统PATH
echo.
echo 2. Ollama (必需):
echo    下载: https://ollama.ai/download
echo    安装后运行以下命令下载模型:
echo    ollama pull qwen2.5:7b
echo.
echo ==========================================
echo.

:: 验证安装
echo [验证] 检查关键依赖...
python -c "import torch; print(f'  ✅ PyTorch {torch.__version__} (CUDA: {torch.cuda.is_available()})')"
python -c "import faster_whisper; print('  ✅ faster-whisper')"
python -c "import scenedetect; print('  ✅ PySceneDetect')"
python -c "import moviepy; print('  ✅ MoviePy')"
python -c "import gradio; print('  ✅ Gradio')"
python -c "import edge_tts; print('  ✅ Edge-TTS')"

echo.
echo ==========================================
echo   安装完成！运行 run.bat 启动程序
echo ==========================================
pause

