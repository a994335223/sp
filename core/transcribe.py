# core/transcribe.py - 语音识别
"""
SmartVideoClipper - 语音识别模块

功能: 使用faster-whisper提取视频中的对白
用途: 生成带精确时间戳的字幕

依赖: faster-whisper, torch
"""

import os
import sys
import json

# 关键：在导入 faster_whisper 之前设置 HuggingFace 镜像
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from faster_whisper import WhisperModel

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.gpu_manager import GPUManager


def transcribe_video(video_path: str, output_srt: str = None):
    """
    视频语音转文字（自动适配显卡）
    
    参数:
        video_path: 视频路径
        output_srt: 字幕输出路径（可选）
    
    返回:
        segments: 带时间戳的字幕列表 [{'start': 0.0, 'end': 2.5, 'text': '...'}, ...]
        full_text: 完整文本字符串
    """
    print(f"🎤 开始语音识别: {video_path}")
    print("   （2小时电影约需10-15分钟）")
    
    # 自动根据显存选择模型（也可手动指定）
    config = GPUManager.get_optimal_config()
    
    # 自动检测是否有GPU，没有则使用CPU
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    print(f"   使用设备: {device}, 模型: {config['whisper']}")
    
    model = WhisperModel(
        config['whisper'],  # 自动选择：6GB=small, 8GB=medium, 12GB+=large
        device=device,
        compute_type=compute_type
    )
    
    segments_list, info = model.transcribe(
        video_path,
        language="zh",
        vad_filter=True,         # 语音活动检测
        vad_parameters=dict(
            min_silence_duration_ms=500,  # 500ms静音分段
            speech_pad_ms=200
        ),
        beam_size=5,             # 准确度和速度平衡
        best_of=5
    )
    
    segments = []
    full_text = ""
    
    # 导入敏感词过滤器
    try:
        from content_filter import filter_sensitive_content
        use_filter = True
    except ImportError:
        use_filter = False
    
    for seg in segments_list:
        text = seg.text.strip()
        
        # 过滤敏感词
        if use_filter:
            text, removed = filter_sensitive_content(text)
            if removed:
                print(f"   [FILTER] 语音识别过滤敏感词: {removed}")
        
        segment = {
            'start': seg.start,
            'end': seg.end,
            'text': text
        }
        segments.append(segment)
        full_text += text
    
    print(f"[OK] 识别完成，共 {len(segments)} 个片段")
    
    # [FIX] 释放模型显存
    del model
    GPUManager.clear()
    
    # 保存SRT字幕
    if output_srt:
        save_srt(segments, output_srt)
    
    return segments, full_text


def save_srt(segments: list, output_path: str):
    """保存SRT字幕文件"""
    
    def format_time(seconds):
        """转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    
    print(f"[OK] 字幕已保存: {output_path}")


def save_json(segments: list, output_path: str):
    """保存JSON格式的识别结果"""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] JSON已保存: {output_path}")


# 使用示例
if __name__ == "__main__":
    # 测试语音识别
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        segments, text = transcribe_video(test_video, "字幕.srt")
        print(f"\n全片对白预览: {text[:500]}...")
        
        # 保存JSON
        save_json(segments, "segments.json")
    else:
        print(f"[WARNING] 测试视频不存在: {test_video}")
        print("请提供一个视频文件进行测试")
