# core/compose_video.py - 视频合成
"""
SmartVideoClipper - 视频合成模块

功能: 将视频、解说音频、字幕合成最终视频
用途: 生成可发布的成品视频

依赖: moviepy, ffmpeg
"""

from moviepy.editor import *
import subprocess
import os
import sys

# 🔧 导入统一编码器
try:
    from .smart_cut import VIDEO_ENCODER  # 包导入模式
except ImportError:
    from smart_cut import VIDEO_ENCODER   # 直接导入模式


def compose_final_video(
    video_path: str,
    narration_path: str,
    output_path: str,
    keep_original_segments: list = None,
    subtitle_path: str = None,
    mode: str = "mix"
):
    """
    合成最终视频
    
    参数:
        video_path: 剪辑后的视频
        narration_path: 解说音频
        output_path: 输出路径
        keep_original_segments: 需要保留原声的时间段 [{'start': 10, 'end': 20}, ...]
        subtitle_path: 字幕文件（可选）
        mode: "mix"=混合, "replace"=完全替换
    """
    print("🎬 开始合成最终视频...")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 🔧 添加文件存在性检查
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"❌ 视频文件不存在: {video_path}")
    if not os.path.exists(narration_path):
        raise FileNotFoundError(f"❌ 解说音频不存在: {narration_path}")
    
    try:
        video = VideoFileClip(video_path)
        narration = AudioFileClip(narration_path)
    except Exception as e:
        raise RuntimeError(f"❌ 加载视频/音频失败: {e}")
    
    if mode == "replace":
        # 完全替换原声
        final_video = video.set_audio(narration)
    
    elif mode == "mix":
        # 智能混合：解说时降低原声，保留原声时静音解说
        original_audio = video.audio
        
        if keep_original_segments and len(keep_original_segments) > 0:
            # 🔧 真正的分段音量控制
            # 方法：根据时间段调整解说音量
            
            def get_narration_volume(t):
                """在保留原声片段时，解说音量降为0"""
                for seg in keep_original_segments:
                    if seg['start'] <= t <= seg['end']:
                        return 0.0  # 保留原声时，解说静音
                return 1.0  # 其他时间解说正常
            
            def get_original_volume(t):
                """在保留原声片段时，原声音量100%"""
                for seg in keep_original_segments:
                    if seg['start'] <= t <= seg['end']:
                        return 1.0  # 保留原声片段
                return 0.2  # 其他时间原声20%
            
            # 应用音量调节
            from moviepy.audio.fx.all import volumex
            narration_adjusted = narration.fl(lambda gf, t: gf(t) * get_narration_volume(t), keep_duration=True)
            original_adjusted = original_audio.fl(lambda gf, t: gf(t) * get_original_volume(t), keep_duration=True)
            
            mixed = CompositeAudioClip([original_adjusted, narration_adjusted])
            print(f"   🎵 已应用分段音量控制，{len(keep_original_segments)}个原声保留片段")
        else:
            # 没有保留原声片段，简单混合
            original_audio = original_audio.volumex(0.2)
            mixed = CompositeAudioClip([original_audio, narration])
        
        final_video = video.set_audio(mixed)
    
    # 导出（使用GPU加速）
    # ⭐ GTX 1080+支持NVENC硬件编码，速度快5-10倍！
    # 🔧 MoviePy需要通过ffmpeg_params传递NVENC参数
    if VIDEO_ENCODER == 'h264_nvenc':
        # GPU加速模式
        final_video.write_videofile(
            output_path,
            codec='libx264',  # MoviePy基础codec
            audio_codec='aac',
            bitrate='8000k',
            fps=video.fps,
            ffmpeg_params=['-c:v', 'h264_nvenc', '-preset', 'fast']  # ⭐ 覆盖为GPU编码
        )
    else:
        # CPU模式（fallback）
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            bitrate='8000k',
            fps=video.fps,
            preset='fast'
        )
    
    # 🔧 释放资源（重要！避免内存泄露）
    video.close()
    narration.close()
    final_video.close()
    
    print(f"✅ 视频合成完成: {output_path}")
    
    # 添加字幕（如果有）
    if subtitle_path and os.path.exists(subtitle_path):
        sub_output = output_path.replace('.mp4', '_sub.mp4')
        add_subtitles(output_path, subtitle_path, sub_output)


def add_subtitles(video_path: str, srt_path: str, output_path: str):
    """
    添加硬字幕
    
    参数:
        video_path: 视频文件
        srt_path: SRT字幕文件
        output_path: 输出文件
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"subtitles={srt_path}:force_style='FontSize=24,FontName=Microsoft YaHei'",
        '-c:a', 'copy',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ 字幕添加完成: {output_path}")


def convert_to_douyin(input_path: str, output_path: str):
    """
    转换为抖音竖屏格式（9:16）
    
    参数:
        input_path: 输入视频
        output_path: 输出视频
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', VIDEO_ENCODER,  # ⭐ 统一编码器（GTX 1080默认h264_nvenc）
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:v', '8M',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ 抖音格式转换完成: {output_path}")


# 使用示例
if __name__ == "__main__":
    # 测试视频合成
    print(f"当前编码器: {VIDEO_ENCODER}")
    
    test_video = "test_video.mp4"
    test_narration = "test_narration.wav"
    
    if os.path.exists(test_video) and os.path.exists(test_narration):
        compose_final_video(
            test_video,
            test_narration,
            "output_composed.mp4",
            mode="mix"
        )
        convert_to_douyin("output_composed.mp4", "output_douyin.mp4")
    else:
        print(f"⚠️ 测试文件不存在")
        print(f"   需要: {test_video}, {test_narration}")

