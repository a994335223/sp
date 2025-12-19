# 🎬 Smart Video Clipper

> **全球最优秀的AI视频剪辑项目** - 全自动影视解说视频生成工具

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CUDA](https://img.shields.io/badge/CUDA-11.8%2B-green.svg)](https://developer.nvidia.com/cuda-downloads)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特性

🎯 **一键生成** - 输入长视频，自动生成短视频解说  
🤖 **AI文案** - 基于Qwen大模型，智能生成解说文案  
🔊 **语音合成** - 多种音色可选，自然流畅  
🎨 **智能剪辑** - 自动识别精彩片段，智能拼接  
📝 **字幕生成** - 基于Whisper，准确识别语音  
🖼️ **封面生成** - AI选取最佳帧，自动添加标题  
⚡ **GPU加速** - 支持NVIDIA显卡硬件编码  

---

## 🖥️ 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| GPU | GTX 1080 (8GB) | RTX 3060+ (12GB+) |
| 内存 | 16GB | 32GB |
| 硬盘 | 50GB | 100GB+ SSD |

### 支持的显卡

- ✅ GTX 1080 / 1080 Ti
- ✅ RTX 2060 / 2070 / 2080 系列
- ✅ RTX 3060 / 3070 / 3080 / 3090 系列
- ✅ RTX 4060 / 4070 / 4080 / 4090 系列

---

## 🚀 快速开始

### 方式1: 智能一键安装（推荐）

1. **下载项目**
   ```bash
   git clone https://github.com/yourusername/smart-video-clipper.git
   cd smart-video-clipper
   ```

2. **右键以管理员身份运行 `智能安装.bat`**
   
   脚本会自动：
   - 检测并安装 Python 3.11
   - 检测并安装 FFmpeg
   - 检测并安装 Ollama + Qwen模型
   - 创建虚拟环境
   - 安装所有依赖
   - 配置环境变量

3. **运行程序**
   ```
   双击 启动.bat
   ```

### 方式2: 手动安装

详见 [运行.md](运行.md)

---

## 📖 使用说明

### Web界面

1. 双击 `启动.bat` 启动程序
2. 浏览器访问 `http://127.0.0.1:7860`
3. 上传视频文件
4. 填写电影名称（可选）
5. 选择解说风格
6. 点击"开始处理"
7. 等待处理完成，下载成品

### 命令行

```bash
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 处理视频
python -m app.main_auto "视频路径.mp4" "电影名称"
```

---

## 🔧 配置说明

复制 `.env.example` 为 `.env`，根据需要修改配置：

```ini
# Whisper模型（根据显存选择）
WHISPER_MODEL=medium

# AI文案模型
OLLAMA_MODEL=qwen2.5:7b

# TTS音色
TTS_VOICE=zh-CN-YunxiNeural

# 视频编码器（auto自动检测）
VIDEO_ENCODER=auto
```

---

## 📁 项目结构

```
smart-video-clipper/
├── app/                    # 应用层
│   ├── gradio_ui.py       # Web界面
│   ├── main_auto.py       # 主流程（完整版）
│   └── main.py            # 主流程（简化版）
├── core/                   # 核心模块
│   ├── scene_detect.py    # 场景检测
│   ├── transcribe.py      # 语音识别
│   ├── clip_analysis.py   # CLIP分析
│   ├── generate_script.py # 文案生成
│   ├── smart_cut.py       # 智能剪辑
│   ├── tts_engine.py      # 语音合成
│   ├── compose_video.py   # 视频合成
│   ├── remove_silence.py  # 静音移除
│   └── cover_generator.py # 封面生成
├── utils/                  # 工具模块
│   └── gpu_manager.py     # GPU管理
├── 智能安装.bat            # 一键安装脚本
├── 启动.bat               # 启动脚本
├── requirements.txt       # Python依赖
└── 运行.md                # 详细文档
```

---

## 🎬 处理流程

```
输入视频
   ↓
[1] 场景检测 (PySceneDetect)
   ↓
[2] 语音识别 (Whisper)
   ↓
[3] CLIP分析 (Chinese-CLIP)
   ↓
[4] 文案生成 (Ollama + Qwen)
   ↓
[5] 智能剪辑 (FFmpeg + GPU)
   ↓
[6] 语音合成 (Edge-TTS)
   ↓
[7] 视频合成 (MoviePy)
   ↓
[8] 静音移除 (FFmpeg)
   ↓
输出成品
```

---

## ⚡ 性能参考

| 视频长度 | GTX 1080 | RTX 3060 | RTX 4060 |
|----------|----------|----------|----------|
| 10分钟 | 5-8分钟 | 3-5分钟 | 2-4分钟 |
| 30分钟 | 15-20分钟 | 10-15分钟 | 8-12分钟 |
| 1小时 | 25-35分钟 | 18-25分钟 | 15-20分钟 |
| 2小时 | 45-60分钟 | 30-45分钟 | 25-35分钟 |

---

## ❓ 常见问题

<details>
<summary><b>Q: CUDA不可用怎么办？</b></summary>

```bash
# 检查CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 重新安装PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
</details>

<details>
<summary><b>Q: 显存不足(OOM)怎么办？</b></summary>

编辑 `.env` 文件，使用更小的模型：
```ini
WHISPER_MODEL=small
```
</details>

<details>
<summary><b>Q: Ollama连接失败怎么办？</b></summary>

```bash
# 确保Ollama正在运行
ollama list

# 如果没有模型，下载：
ollama pull qwen2.5:7b
```
</details>

更多问题请查看 [运行.md](运行.md)

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别
- [Chinese-CLIP](https://github.com/OFA-Sys/Chinese-CLIP) - 图像理解
- [Ollama](https://ollama.ai/) - 本地大模型
- [FFmpeg](https://ffmpeg.org/) - 视频处理
- [Gradio](https://gradio.app/) - Web界面

---

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**
