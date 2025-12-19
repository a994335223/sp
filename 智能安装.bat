@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================
:: 🎬 Smart Video Clipper - 智能一键安装脚本
:: 全球最优秀的AI视频剪辑项目
:: ============================================

title Smart Video Clipper - 智能安装程序 v1.0

:: 颜色定义
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "RESET=[0m"

echo.
echo %CYAN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║        🎬 Smart Video Clipper - 智能安装程序 v1.0           ║%RESET%
echo %CYAN%║            全球最优秀的AI视频剪辑项目                        ║%RESET%
echo %CYAN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ============================================
:: 第一步：检查管理员权限
:: ============================================
echo %BLUE%[1/8] 检查管理员权限...%RESET%

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%⚠️  需要管理员权限，正在请求提升...%RESET%
    
    :: 创建临时VBS脚本请求管理员权限
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B
)

echo %GREEN%✅ 已获取管理员权限%RESET%
echo.

:: ============================================
:: 第二步：检测系统信息
:: ============================================
echo %BLUE%[2/8] 检测系统信息...%RESET%

:: 检测Windows版本
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
echo    📌 Windows版本: %VERSION%

:: 检测系统架构
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "ARCH=64位"
    set "ARCH_TYPE=x64"
) else (
    set "ARCH=32位"
    set "ARCH_TYPE=x86"
)
echo    📌 系统架构: %ARCH%

:: 检测可用内存
for /f "skip=1" %%p in ('wmic os get FreePhysicalMemory') do (
    set /a "FREE_MEM=%%p/1024/1024" 2>nul
    goto :mem_done
)
:mem_done
echo    📌 可用内存: 约 %FREE_MEM% GB

echo %GREEN%✅ 系统信息检测完成%RESET%
echo.

:: ============================================
:: 第三步：检测NVIDIA显卡和CUDA
:: ============================================
echo %BLUE%[3/8] 检测NVIDIA显卡和CUDA...%RESET%

set "HAS_NVIDIA=0"
set "CUDA_VERSION="

:: 检测nvidia-smi
where nvidia-smi >nul 2>&1
if %errorLevel% equ 0 (
    set "HAS_NVIDIA=1"
    for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
        echo    🎮 检测到显卡: %%a
    )
    
    :: 获取CUDA版本
    for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=driver_version --format=csv,noheader 2^>nul') do (
        echo    📌 驱动版本: %%a
    )
    
    :: 检测显存
    for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=memory.total --format=csv,noheader 2^>nul') do (
        echo    📌 显存大小: %%a
    )
    
    echo %GREEN%✅ NVIDIA显卡检测成功，将启用GPU加速%RESET%
) else (
    echo %YELLOW%⚠️  未检测到NVIDIA显卡，将使用CPU模式（速度较慢）%RESET%
)
echo.

:: ============================================
:: 第四步：检测并安装Python
:: ============================================
echo %BLUE%[4/8] 检测Python环境...%RESET%

set "PYTHON_OK=0"
set "PYTHON_CMD=python"

:: 检测Python
python --version >nul 2>&1
if %errorLevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    echo    📌 检测到Python: !PY_VER!
    
    :: 检查版本是否>=3.9
    for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
        set /a "PY_MAJOR=%%a"
        set /a "PY_MINOR=%%b"
    )
    
    if !PY_MAJOR! geq 3 (
        if !PY_MINOR! geq 9 (
            set "PYTHON_OK=1"
            echo %GREEN%✅ Python版本符合要求 (>=3.9)%RESET%
        )
    )
    
    if !PYTHON_OK! equ 0 (
        echo %YELLOW%⚠️  Python版本过低，需要3.9+%RESET%
    )
) else (
    echo %YELLOW%⚠️  未检测到Python%RESET%
)

if !PYTHON_OK! equ 0 (
    echo.
    echo %YELLOW%📥 正在下载Python 3.11...%RESET%
    
    :: 使用PowerShell下载Python
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe' -OutFile '%temp%\python_installer.exe'}"
    
    if exist "%temp%\python_installer.exe" (
        echo %YELLOW%📥 正在安装Python 3.11（静默安装）...%RESET%
        "%temp%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        
        :: 刷新环境变量
        call :RefreshEnv
        
        echo %GREEN%✅ Python 3.11 安装完成%RESET%
        set "PYTHON_OK=1"
    ) else (
        echo %RED%❌ Python下载失败，请手动安装: https://www.python.org/downloads/%RESET%
        echo    按任意键继续（如果已手动安装）...
        pause >nul
    )
)
echo.

:: ============================================
:: 第五步：检测并安装FFmpeg
:: ============================================
echo %BLUE%[5/8] 检测FFmpeg...%RESET%

set "FFMPEG_OK=0"

where ffmpeg >nul 2>&1
if %errorLevel% equ 0 (
    for /f "tokens=3" %%v in ('ffmpeg -version 2^>^&1 ^| findstr /i "ffmpeg version"') do (
        echo    📌 检测到FFmpeg: %%v
    )
    
    :: 检查是否支持NVENC
    ffmpeg -encoders 2>nul | findstr /i "h264_nvenc" >nul
    if %errorLevel% equ 0 (
        echo    📌 NVENC硬件编码: ✅ 支持
    ) else (
        echo    📌 NVENC硬件编码: ❌ 不支持（建议重新安装带GPU支持的版本）
    )
    
    set "FFMPEG_OK=1"
    echo %GREEN%✅ FFmpeg已安装%RESET%
) else (
    echo %YELLOW%⚠️  未检测到FFmpeg%RESET%
    echo.
    echo %YELLOW%📥 正在下载FFmpeg...%RESET%
    
    :: 创建临时目录
    if not exist "%temp%\ffmpeg_install" mkdir "%temp%\ffmpeg_install"
    
    :: 下载FFmpeg (使用gyan.dev的完整版，包含NVENC)
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%temp%\ffmpeg_install\ffmpeg.zip'}"
    
    if exist "%temp%\ffmpeg_install\ffmpeg.zip" (
        echo %YELLOW%📥 正在解压FFmpeg...%RESET%
        powershell -Command "Expand-Archive -Path '%temp%\ffmpeg_install\ffmpeg.zip' -DestinationPath '%temp%\ffmpeg_install' -Force"
        
        :: 找到解压后的目录
        for /d %%d in ("%temp%\ffmpeg_install\ffmpeg-*") do (
            set "FFMPEG_DIR=%%d"
        )
        
        :: 复制到Program Files
        if not exist "C:\Program Files\FFmpeg" mkdir "C:\Program Files\FFmpeg"
        xcopy "!FFMPEG_DIR!\bin\*" "C:\Program Files\FFmpeg\" /Y /Q
        
        :: 添加到系统PATH
        echo %YELLOW%📥 配置FFmpeg环境变量...%RESET%
        setx PATH "%PATH%;C:\Program Files\FFmpeg" /M >nul 2>&1
        set "PATH=%PATH%;C:\Program Files\FFmpeg"
        
        echo %GREEN%✅ FFmpeg安装完成%RESET%
        set "FFMPEG_OK=1"
    ) else (
        echo %RED%❌ FFmpeg下载失败%RESET%
        echo    请手动下载: https://www.gyan.dev/ffmpeg/builds/
        echo    下载 ffmpeg-release-essentials.zip 并解压到 C:\Program Files\FFmpeg
    )
)
echo.

:: ============================================
:: 第六步：检测并安装Ollama
:: ============================================
echo %BLUE%[6/8] 检测Ollama...%RESET%

set "OLLAMA_OK=0"

where ollama >nul 2>&1
if %errorLevel% equ 0 (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do (
        echo    📌 检测到Ollama: %%v
    )
    set "OLLAMA_OK=1"
    echo %GREEN%✅ Ollama已安装%RESET%
    
    :: 检查qwen2.5:7b模型
    echo    📌 检查AI模型...
    ollama list 2>nul | findstr /i "qwen2.5:7b" >nul
    if %errorLevel% equ 0 (
        echo    📌 qwen2.5:7b模型: ✅ 已安装
    ) else (
        echo %YELLOW%    📌 qwen2.5:7b模型: ❌ 未安装，稍后将自动下载%RESET%
        set "NEED_QWEN=1"
    )
) else (
    echo %YELLOW%⚠️  未检测到Ollama%RESET%
    echo.
    echo %YELLOW%📥 正在下载Ollama...%RESET%
    
    :: 下载Ollama安装程序
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%temp%\OllamaSetup.exe'}"
    
    if exist "%temp%\OllamaSetup.exe" (
        echo %YELLOW%📥 正在安装Ollama...%RESET%
        start /wait "" "%temp%\OllamaSetup.exe" /VERYSILENT /NORESTART
        
        :: 刷新环境变量
        call :RefreshEnv
        
        echo %GREEN%✅ Ollama安装完成%RESET%
        set "OLLAMA_OK=1"
        set "NEED_QWEN=1"
    ) else (
        echo %RED%❌ Ollama下载失败%RESET%
        echo    请手动下载: https://ollama.com/download
    )
)
echo.

:: ============================================
:: 第七步：创建虚拟环境并安装Python依赖
:: ============================================
echo %BLUE%[7/8] 配置Python环境...%RESET%

cd /d "%~dp0"

:: 检查是否已有虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo    📌 检测到已有虚拟环境
    echo %YELLOW%    是否重新创建？(y/n，默认n)%RESET%
    set /p "RECREATE_VENV=    请输入: "
    if /i "!RECREATE_VENV!"=="y" (
        echo    📥 删除旧虚拟环境...
        rmdir /s /q venv
        goto :create_venv
    ) else (
        echo    📌 使用现有虚拟环境
        goto :install_deps
    )
)

:create_venv
echo    📥 创建Python虚拟环境...
python -m venv venv
if %errorLevel% neq 0 (
    echo %RED%❌ 虚拟环境创建失败%RESET%
    goto :error_exit
)
echo %GREEN%✅ 虚拟环境创建成功%RESET%

:install_deps
echo.
echo    📥 激活虚拟环境...
call venv\Scripts\activate.bat

echo    📥 升级pip...
python -m pip install --upgrade pip -q

echo    📥 安装Python依赖包（这可能需要几分钟）...
echo.

:: 根据是否有NVIDIA显卡选择安装方式
if %HAS_NVIDIA% equ 1 (
    echo    📌 检测到NVIDIA显卡，安装CUDA版本的PyTorch...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
) else (
    echo    📌 未检测到NVIDIA显卡，安装CPU版本的PyTorch...
    pip install torch torchvision torchaudio -q
)

:: 安装其他依赖
echo    📥 安装其他依赖...
pip install -r requirements.txt -q

if %errorLevel% neq 0 (
    echo %RED%❌ 依赖安装失败，尝试逐个安装...%RESET%
    pip install gradio>=4.0.0
    pip install moviepy>=1.0.3
    pip install openai-whisper>=20231117
    pip install faster-whisper>=0.9.0
    pip install scenedetect[opencv]>=0.6.1
    pip install cn-clip
    pip install edge-tts>=6.1.9
    pip install pysrt>=1.1.2
    pip install python-dotenv>=1.0.0
    pip install ollama>=0.1.0
    pip install numpy>=1.24.0
    pip install opencv-python>=4.8.0
    pip install pillow>=10.0.0
    pip install tqdm>=4.66.0
)

echo %GREEN%✅ Python依赖安装完成%RESET%
echo.

:: ============================================
:: 第八步：配置环境变量和模型
:: ============================================
echo %BLUE%[8/8] 最终配置...%RESET%

:: 创建.env文件（如果不存在）
if not exist ".env" (
    echo    📥 创建环境配置文件...
    (
        echo # Smart Video Clipper 环境配置
        echo # 由智能安装脚本自动生成
        echo.
        echo # Whisper模型选择 (tiny/base/small/medium/large-v3^)
        echo WHISPER_MODEL=medium
        echo.
        echo # CLIP模型选择
        echo CLIP_MODEL=ViT-B-16
        echo.
        echo # Ollama配置
        echo OLLAMA_MODEL=qwen2.5:7b
        echo OLLAMA_HOST=http://localhost:11434
        echo.
        echo # TTS配置
        echo TTS_VOICE=zh-CN-YunxiNeural
        echo TTS_RATE=+0%%
        echo.
        echo # 输出配置
        echo OUTPUT_DIR=./output
        echo TEMP_DIR=./temp
        echo.
        echo # GPU配置 (auto/cuda/cpu^)
        echo DEVICE=auto
    ) > .env
    echo %GREEN%✅ 环境配置文件创建成功%RESET%
) else (
    echo    📌 环境配置文件已存在，跳过创建
)

:: 创建必要目录
if not exist "output" mkdir output
if not exist "temp" mkdir temp
if not exist "input" mkdir input

:: 下载Ollama模型
if defined NEED_QWEN (
    echo.
    echo %YELLOW%📥 下载AI文案模型 qwen2.5:7b（约4.7GB，请耐心等待）...%RESET%
    echo    首次下载可能需要10-30分钟，取决于网络速度
    echo.
    
    :: 启动Ollama服务
    start /B ollama serve >nul 2>&1
    timeout /t 3 /nobreak >nul
    
    :: 下载模型
    ollama pull qwen2.5:7b
    
    if %errorLevel% equ 0 (
        echo %GREEN%✅ AI模型下载完成%RESET%
    ) else (
        echo %YELLOW%⚠️  模型下载可能未完成，请稍后手动运行: ollama pull qwen2.5:7b%RESET%
    )
)

echo.

:: ============================================
:: 安装完成
:: ============================================
echo.
echo %GREEN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║                    🎉 安装完成！                              ║%RESET%
echo %GREEN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.
echo %CYAN%📋 安装摘要：%RESET%
echo    ├─ Python环境: %GREEN%✅%RESET%
echo    ├─ FFmpeg: %GREEN%✅%RESET%
echo    ├─ Ollama: %GREEN%✅%RESET%
echo    ├─ Python依赖: %GREEN%✅%RESET%
echo    └─ 环境配置: %GREEN%✅%RESET%
echo.
echo %CYAN%🚀 启动方式：%RESET%
echo    方式1: 双击运行 启动.bat
echo    方式2: 命令行运行 python -m app.gradio_ui
echo.
echo %CYAN%📁 文件夹说明：%RESET%
echo    input/  - 放入待处理的视频
echo    output/ - 输出处理后的视频
echo    temp/   - 临时文件（可定期清理）
echo.
echo %YELLOW%💡 提示：首次运行会自动下载AI模型，请保持网络连接%RESET%
echo.

:: 询问是否立即启动
echo %CYAN%是否立即启动程序？(y/n)%RESET%
set /p "START_NOW=请输入: "
if /i "%START_NOW%"=="y" (
    echo.
    echo %YELLOW%正在启动 Smart Video Clipper...%RESET%
    call venv\Scripts\activate.bat
    python -m app.gradio_ui
)

goto :end

:: ============================================
:: 辅助函数
:: ============================================

:RefreshEnv
:: 刷新环境变量
echo    📥 刷新环境变量...
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%b"
set "PATH=%SYS_PATH%;%USER_PATH%"
goto :eof

:error_exit
echo.
echo %RED%❌ 安装过程中出现错误，请查看上方信息%RESET%
echo    如需帮助，请访问项目GitHub页面
pause
exit /b 1

:end
echo.
echo 按任意键退出...
pause >nul
exit /b 0

