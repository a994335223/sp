# core/compose_video.py - 视频合成
"""
SmartVideoClipper - 视频合成模块

功能: 将视频、解说音频、字幕合成最终视频
用途: 生成可发布的成品视频

依赖: moviepy, ffmpeg
"""

import subprocess
import os
import sys

# MoviePy 2.x 兼容导入
try:
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
except ImportError:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

# 导入统一编码器
try:
    from .smart_cut import VIDEO_ENCODER
except ImportError:
    from smart_cut import VIDEO_ENCODER


def compose_final_video(
    video_path: str,
    narration_path: str,
    output_path: str,
    keep_original_segments: list = None,
    subtitle_path: str = None,
    mode: str = "replace"  # [FIX] 默认改为replace，确保解说为主
):
    """
    合成最终视频
    
    参数:
        video_path: 剪辑后的视频
        narration_path: 解说音频
        output_path: 输出路径
        keep_original_segments: 需要保留原声的时间段（仅mix模式有效）
        subtitle_path: 字幕文件（可选）
        mode: 
            - "replace": 完全替换原声为解说（推荐，确保解说清晰）
            - "mix": 混合模式，解说音量100%，原声降到10%作为背景
    """
    print("[VIDEO] 开始合成最终视频...")
    print(f"   合成模式: {mode}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 文件检查
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"[ERROR] 视频文件不存在: {video_path}")
    if not os.path.exists(narration_path):
        raise FileNotFoundError(f"[ERROR] 解说音频不存在: {narration_path}")
    
    try:
        video = VideoFileClip(video_path)
        narration = AudioFileClip(narration_path)
    except Exception as e:
        raise RuntimeError(f"[ERROR] 加载视频/音频失败: {e}")
    
    # 检测 MoviePy 版本并选择正确的方法
    has_with_audio = hasattr(video, 'with_audio')
    
    # 获取视频和解说时长
    video_duration = video.duration
    narration_duration = narration.duration
    print(f"   视频时长: {video_duration:.1f}秒")
    print(f"   解说时长: {narration_duration:.1f}秒")
    
    try:
        if mode == "replace":
            # [推荐] 完全替换原声为解说
            print("   使用纯解说模式...")
            if has_with_audio:
                final_video = video.with_audio(narration)
            else:
                final_video = video.set_audio(narration)
        
        elif mode == "mix":
            # 混合模式：解说为主，原声为辅
            original_audio = video.audio
            
            if original_audio is None:
                # 视频没有音轨，直接使用解说
                print("   视频无音轨，使用纯解说...")
                if has_with_audio:
                    final_video = video.with_audio(narration)
                else:
                    final_video = video.set_audio(narration)
            else:
                # [FIX] 改进混合逻辑：解说100%，原声降到10%作为背景
                print("   混合模式：解说100% + 原声10%背景...")
                try:
                    # MoviePy 2.x 方式
                    if hasattr(original_audio, 'with_volume_scaled'):
                        original_low = original_audio.with_volume_scaled(0.1)  # 原声降到10%
                    else:
                        original_low = original_audio.volumex(0.1)  # 原声降到10%
                    
                    # 确保解说音量正常（100%）
                    # 解说在前（优先级更高）
                    mixed = CompositeAudioClip([narration, original_low])
                    
                    if has_with_audio:
                        final_video = video.with_audio(mixed)
                    else:
                        final_video = video.set_audio(mixed)
                        
                except Exception as e:
                    print(f"   [WARNING] 音频混合失败: {e}，切换到纯解说模式")
                    if has_with_audio:
                        final_video = video.with_audio(narration)
                    else:
                        final_video = video.set_audio(narration)
        
        else:
            # 未知模式，默认替换
            print(f"   [WARNING] 未知模式'{mode}'，使用纯解说...")
            if has_with_audio:
                final_video = video.with_audio(narration)
            else:
                final_video = video.set_audio(narration)
        
        # 导出
        print("   正在导出视频...")
        fps = video.fps if video.fps else 24
        
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            bitrate='8000k',
            fps=fps,
            preset='fast',
            logger=None  # 禁用进度条避免乱码
        )
        
    finally:
        # 释放资源
        try:
            video.close()
        except:
            pass
        try:
            narration.close()
        except:
            pass
        try:
            if 'final_video' in locals():
                final_video.close()
        except:
            pass
    
    # 验证输出
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError("[ERROR] 视频导出失败")
    
    print(f"[OK] 视频合成完成: {output_path}")
    
    # 添加字幕（如果有）
    if subtitle_path and os.path.exists(subtitle_path):
        sub_output = output_path.replace('.mp4', '_sub.mp4')
        add_subtitles(output_path, subtitle_path, sub_output)


def add_subtitles(video_path: str, srt_path: str, output_path: str):
    """添加硬字幕"""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 处理路径中的特殊字符
    srt_path_escaped = srt_path.replace('\\', '/').replace(':', '\\:')
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"subtitles='{srt_path_escaped}':force_style='FontSize=24,FontName=Microsoft YaHei'",
        '-c:a', 'copy',
        '-loglevel', 'error',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if os.path.exists(output_path):
        print(f"[OK] 字幕添加完成: {output_path}")
    else:
        print(f"[WARNING] 字幕添加失败: {result.stderr[:100] if result.stderr else 'unknown'}")


def convert_to_douyin(input_path: str, output_path: str):
    """转换为抖音竖屏格式（9:16）"""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 优先尝试 GPU 编码
    encoder = VIDEO_ENCODER if VIDEO_ENCODER else 'libx264'
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', encoder,
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:v', '8M',
        '-loglevel', 'error',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # 如果 GPU 失败，尝试 CPU
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        if encoder != 'libx264':
            print("   [INFO] GPU编码失败，使用CPU...")
            cmd[cmd.index(encoder)] = 'libx264'
            result = subprocess.run(cmd, capture_output=True, text=True)
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"[OK] 抖音格式转换完成: {output_path}")
    else:
        raise RuntimeError(f"[ERROR] 抖音格式转换失败: {result.stderr[:200] if result.stderr else 'unknown'}")


if __name__ == "__main__":
    print(f"当前编码器: {VIDEO_ENCODER}")
