# utils/dependency_check.py - 启动时依赖检查
"""
SmartVideoClipper - 依赖检查模块

功能:
1. 检查Python包是否已安装
2. 检查外部工具是否可用（FFmpeg, Ollama）
3. 检查Ollama模型是否已下载
"""

import sys
import subprocess


def check_dependencies():
    """检查所有依赖是否已安装"""
    print("🔍 检查依赖...")
    
    # 必需的Python包
    required_packages = {
        'torch': 'PyTorch (深度学习框架)',
        'faster_whisper': 'faster-whisper (语音识别)',
        'scenedetect': 'PySceneDetect (镜头检测)',
        'moviepy': 'MoviePy (视频处理)',
        'gradio': 'Gradio (Web界面)',
        'edge_tts': 'Edge-TTS (语音合成)',
        'ollama': 'Ollama (AI文案生成)',
        'httpx': 'httpx (HTTP客户端)',
        'bs4': 'BeautifulSoup (网页解析)',
    }
    
    # 可选的Python包
    optional_packages = {
        'cn_clip': 'Chinese-CLIP (画面分析-国内版)',
        'ChatTTS': 'ChatTTS (高质量TTS-可选)',
    }
    
    missing_required = []
    missing_optional = []
    
    # 检查必需包
    print("\n📦 必需依赖:")
    for pkg, desc in required_packages.items():
        try:
            __import__(pkg)
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} - {desc}")
            missing_required.append(pkg)
    
    # 检查可选包
    print("\n📦 可选依赖:")
    for pkg, desc in optional_packages.items():
        try:
            __import__(pkg)
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ⚠️ {pkg} - {desc} (可选)")
            missing_optional.append(pkg)
    
    # 检查FFmpeg
    print("\n🔧 外部工具:")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  ✅ FFmpeg - {version[:50]}")
        else:
            print("  ❌ FFmpeg - 未找到")
            missing_required.append('ffmpeg')
    except FileNotFoundError:
        print("  ❌ FFmpeg - 未安装")
        missing_required.append('ffmpeg')
    
    # 检查Ollama
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Ollama - {result.stdout.strip()}")
            
            # 检查Qwen模型是否已下载
            model_result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if 'qwen2.5' in model_result.stdout:
                print("  ✅ Qwen模型已下载")
            else:
                print("  ⚠️ Qwen模型未下载，请运行: ollama pull qwen2.5:7b")
        else:
            print("  ❌ Ollama - 未找到")
            missing_required.append('ollama')
    except FileNotFoundError:
        print("  ❌ Ollama - 未安装")
        missing_required.append('ollama')
    
    # 结果总结
    print("\n" + "=" * 50)
    if missing_required:
        print("❌ 缺少必需依赖，请运行 install_all.bat 安装")
        print(f"   缺少: {', '.join(missing_required)}")
        return False, missing_required
    else:
        print("✅ 所有必需依赖已安装！")
        if missing_optional:
            print(f"⚠️ 可选依赖未安装: {', '.join(missing_optional)}")
        return True, []


def check_gpu():
    """检查GPU状态"""
    print("\n🎮 GPU检测:")
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024 / 1024
            print(f"  ✅ CUDA可用")
            print(f"  📍 设备: {device_name}")
            print(f"  💾 显存: {total_memory:.1f}GB")
            
            # 检查NVENC支持
            result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
            if 'h264_nvenc' in result.stdout:
                print("  🚀 NVENC硬件编码: 支持")
            else:
                print("  ⚠️ NVENC硬件编码: 不支持（将使用CPU编码）")
            
            return True
        else:
            print("  ⚠️ CUDA不可用，将使用CPU模式（速度较慢）")
            return False
    except ImportError:
        print("  ❌ PyTorch未安装")
        return False


# 启动时自动检查
if __name__ == "__main__":
    print("=" * 50)
    print("SmartVideoClipper - 依赖检查")
    print("=" * 50)
    
    success, missing = check_dependencies()
    check_gpu()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有检查通过，可以启动程序！")
    else:
        print("⚠️ 请先安装缺少的依赖")
        sys.exit(1)

