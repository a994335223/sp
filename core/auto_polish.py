# core/auto_polish.py - 自动润色（替代手动DaVinci操作）
"""
SmartVideoClipper - 自动润色模块

功能: 使用FFmpeg滤镜自动添加转场、调色
用途: 无需手动操作DaVinci Resolve也能获得专业效果

依赖: ffmpeg
"""

import subprocess
import os
import sys

# [FIX] 导入统一编码器（使用相对导入）
try:
    from .smart_cut import VIDEO_ENCODER  # 包导入模式
except ImportError:
    from smart_cut import VIDEO_ENCODER   # 直接导入模式


def apply_cinematic_filter(video_path: str, style: str = "cinematic", output_path: str = None):
    """
    应用电影级调色滤镜
    
    参数:
        video_path: 输入视频
        style: 滤镜风格
            - "cinematic": 电影色调（推荐）
            - "warm": 暖色调
            - "cool": 冷色调
            - "vintage": 复古风格
            - "dramatic": 戏剧性对比
        output_path: 输出路径（默认覆盖添加后缀）
    
    返回:
        输出文件路径
    """
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_{style}{ext}"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 滤镜配置
    filters = {
        "cinematic": "eq=contrast=1.1:brightness=0.02:saturation=1.2,curves=m='0/0 0.25/0.20 0.5/0.5 0.75/0.85 1/1'",
        "warm": "colorbalance=rs=0.1:gs=0.05:bs=-0.1,eq=saturation=1.1",
        "cool": "colorbalance=rs=-0.1:gs=0:bs=0.15,eq=contrast=1.05",
        "vintage": "curves=vintage,eq=saturation=0.9:brightness=0.05",
        "dramatic": "eq=contrast=1.3:brightness=-0.05:saturation=1.1,unsharp=5:5:0.8"
    }
    
    color_filter = filters.get(style, filters["cinematic"])
    
    # 添加淡入淡出效果
    fade_filter = "fade=t=in:st=0:d=1,fade=t=out:st=-1:d=1"
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"{color_filter},{fade_filter}",
        '-c:v', VIDEO_ENCODER,  # [STAR] 统一编码器（GTX 1080默认h264_nvenc）
        '-preset', 'fast',
        '-c:a', 'copy',
        output_path
    ]
    
    print(f"🎨 应用{style}风格滤镜...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[OK] 自动润色完成: {output_path}")
    else:
        print(f"[WARNING] 润色处理出错: {result.stderr[:200]}")
    
    return output_path


def add_transitions(clips_dir: str, output_path: str, transition_type: str = "fade"):
    """
    为多个片段添加转场效果
    
    参数:
        clips_dir: 片段目录
        output_path: 输出文件
        transition_type: 转场类型 (fade, dissolve, wipe)
    """
    # 获取所有视频片段
    clips = sorted([
        os.path.join(clips_dir, f) 
        for f in os.listdir(clips_dir) 
        if f.endswith('.mp4')
    ])
    
    if len(clips) < 2:
        print("[WARNING] 片段数量不足，无需添加转场")
        return
    
    print(f"[VIDEO] 为{len(clips)}个片段添加{transition_type}转场...")
    
    # 创建转场滤镜（简化版，实际需要更复杂的filter_complex）
    # 这里使用简单的淡入淡出
    for i, clip in enumerate(clips):
        fade_cmd = [
            'ffmpeg', '-y',
            '-i', clip,
            '-vf', 'fade=t=in:st=0:d=0.5,fade=t=out:st=-0.5:d=0.5',
            '-c:v', VIDEO_ENCODER,
            '-c:a', 'aac',
            clip.replace('.mp4', '_fade.mp4')
        ]
        subprocess.run(fade_cmd, capture_output=True)
    
    print(f"[OK] 转场效果添加完成")


def enhance_audio(video_path: str, output_path: str = None):
    """
    增强音频（标准化音量、降噪）
    
    参数:
        video_path: 输入视频
        output_path: 输出路径
    """
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_enhanced{ext}"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80,lowpass=f=12000',
        '-c:v', 'copy',
        output_path
    ]
    
    print("[TTS] 增强音频...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[OK] 音频增强完成: {output_path}")
    else:
        print(f"[WARNING] 音频增强出错")
    
    return output_path


def add_watermark(video_path: str, text: str, output_path: str = None, position: str = "bottom_right"):
    """
    添加文字水印
    
    参数:
        video_path: 输入视频
        text: 水印文字
        output_path: 输出路径
        position: 位置 (top_left, top_right, bottom_left, bottom_right, center)
    """
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_watermark{ext}"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 位置配置
    positions = {
        "top_left": "x=10:y=10",
        "top_right": "x=w-tw-10:y=10",
        "bottom_left": "x=10:y=h-th-10",
        "bottom_right": "x=w-tw-10:y=h-th-10",
        "center": "x=(w-tw)/2:y=(h-th)/2"
    }
    
    pos = positions.get(position, positions["bottom_right"])
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"drawtext=text='{text}':fontsize=24:fontcolor=white@0.7:{pos}:fontfile=C\\:/Windows/Fonts/msyh.ttc",
        '-c:v', VIDEO_ENCODER,
        '-c:a', 'copy',
        output_path
    ]
    
    print(f"[FILE] 添加水印: {text}")
    subprocess.run(cmd, capture_output=True)
    print(f"[OK] 水印添加完成: {output_path}")
    
    return output_path


# 使用示例
if __name__ == "__main__":
    print(f"当前编码器: {VIDEO_ENCODER}")
    
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        # 测试调色
        apply_cinematic_filter(test_video, "cinematic")
        
        # 测试音频增强
        enhance_audio(test_video)
        
        # 测试水印
        add_watermark(test_video, "@SmartVideoClipper", position="bottom_right")
    else:
        print(f"[WARNING] 测试视频不存在: {test_video}")
