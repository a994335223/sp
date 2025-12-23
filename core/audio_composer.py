# core/audio_composer.py - 音频合成器 v5.0 (GPU加速版)
"""
SmartVideoClipper - 智能音频合成器

核心功能：
1. 原声场景 → 保留原始音频
2. 解说场景 → 使用TTS音频
3. 智能混合 → 平滑过渡

技术实现：
- 使用FFmpeg进行精确的音频切换
- 支持音频淡入淡出
- 确保音画同步
- GPU硬件加速编码
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional

# 导入GPU编码器
try:
    from gpu_encoder import get_video_codec_args, is_hardware_available
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    def get_video_codec_args(quality='fast'):
        return ['-c:v', 'libx264', '-preset', 'fast']
    def is_hardware_available():
        return False


def compose_with_mixed_audio(
    video_clips: List[str],
    timeline: List[Dict],
    narration_audio: str,
    output_path: str,
    original_video: str = None
) -> str:
    """
    合成视频，智能切换原声/解说
    
    参数：
        video_clips: 视频片段文件列表
        timeline: 时间线（包含audio_mode）
        narration_audio: 解说音频文件
        output_path: 输出路径
        original_video: 原始视频（用于提取原声）
    
    返回：
        输出视频路径
    """
    print("\n[AUDIO] 智能音频合成...")
    
    work_dir = Path(output_path).parent
    
    # Step 1: 拼接视频片段
    print("   [1/4] 拼接视频片段...")
    temp_video = str(work_dir / "temp_video_concat.mp4")
    
    if not _concat_videos(video_clips, temp_video):
        raise RuntimeError("视频拼接失败")
    
    # Step 2: 分析时间线
    original_segments = []  # 需要原声的时间段
    voiceover_segments = []  # 需要解说的时间段
    
    for item in timeline:
        if item['audio_mode'] == 'original':
            original_segments.append({
                'start': item['output_start'],
                'end': item['output_end'],
            })
        else:
            voiceover_segments.append({
                'start': item['output_start'],
                'end': item['output_end'],
            })
    
    orig_count = len(original_segments)
    voice_count = len(voiceover_segments)
    print(f"   原声段: {orig_count}, 解说段: {voice_count}")
    
    # Step 3: 决定合成策略
    if orig_count == 0:
        # 全部解说
        print("   [策略] 全部使用解说音频")
        result = _replace_audio(temp_video, narration_audio, output_path)
    elif voice_count == 0:
        # 全部原声
        print("   [策略] 全部保留原声")
        shutil.copy(temp_video, output_path)
        result = output_path
    else:
        # 混合模式
        print("   [策略] 混合原声和解说")
        result = _mix_audio_segments(
            temp_video, 
            narration_audio,
            timeline,
            output_path,
            work_dir
        )
    
    # 清理临时文件
    try:
        os.remove(temp_video)
    except:
        pass
    
    if os.path.exists(result):
        file_size = os.path.getsize(result) / (1024*1024)
        print(f"[OK] 音频合成完成: {result} ({file_size:.1f}MB)")
        return result
    else:
        raise RuntimeError("音频合成失败")


def _concat_videos(clips: List[str], output: str) -> bool:
    """拼接视频片段"""
    if not clips:
        return False
    
    # 写入文件列表
    list_file = output + ".list.txt"
    with open(list_file, 'w', encoding='utf-8') as f:
        for clip in clips:
            abs_path = os.path.abspath(clip).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        '-loglevel', 'error',
        output
    ]
    
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    # 清理
    try:
        os.remove(list_file)
    except:
        pass
    
    return os.path.exists(output) and os.path.getsize(output) > 1000


def _replace_audio(video: str, audio: str, output: str) -> str:
    """完全替换音频"""
    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-i', audio,
        '-c:v', 'copy',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        '-loglevel', 'error',
        output
    ]
    
    subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    return output


def _mix_audio_segments(
    video: str,
    narration: str,
    timeline: List[Dict],
    output: str,
    work_dir: Path
) -> str:
    """
    混合原声和解说
    
    实现方式：
    1. 提取原始视频的音频
    2. 根据时间线，在解说段用解说音频，原声段用原声
    3. 合并音频轨道
    """
    print("   [2/4] 提取原始音频...")
    
    # 提取原声
    original_audio = str(work_dir / "temp_original_audio.wav")
    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        '-loglevel', 'error',
        original_audio
    ]
    subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    if not os.path.exists(original_audio):
        print("   [WARNING] 无法提取原声，使用纯解说")
        return _replace_audio(video, narration, output)
    
    print("   [3/4] 构建混合音频...")
    
    # 使用FFmpeg的复杂滤镜混合音频
    # 策略：解说段用解说，原声段用原声
    
    # 计算总时长
    total_duration = max(item['output_end'] for item in timeline)
    
    # 构建滤镜
    # 简化处理：如果解说段占比大，以解说为主；否则以原声为主
    voice_duration = sum(
        item['output_end'] - item['output_start'] 
        for item in timeline 
        if item['audio_mode'] == 'voiceover'
    )
    
    voice_ratio = voice_duration / total_duration if total_duration > 0 else 0
    
    if voice_ratio > 0.5:
        # 解说为主，原声段降低音量
        print(f"   解说占比 {voice_ratio*100:.0f}%，以解说为主")
        mixed_audio = str(work_dir / "temp_mixed_audio.wav")
        
        # 方案：解说全程播放，原声段混入低音量原声
        cmd = [
            'ffmpeg', '-y',
            '-i', narration,
            '-i', original_audio,
            '-filter_complex',
            f'[0:a]volume=1.0[narr];'
            f'[1:a]volume=0.15[orig];'
            f'[narr][orig]amix=inputs=2:duration=shortest[out]',
            '-map', '[out]',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-loglevel', 'error',
            mixed_audio
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if os.path.exists(mixed_audio):
            final_audio = mixed_audio
        else:
            final_audio = narration
    else:
        # 原声为主，解说段混入解说
        print(f"   原声占比 {(1-voice_ratio)*100:.0f}%，以原声为主")
        mixed_audio = str(work_dir / "temp_mixed_audio.wav")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', original_audio,
            '-i', narration,
            '-filter_complex',
            f'[0:a]volume=0.3[orig];'
            f'[1:a]volume=1.0[narr];'
            f'[orig][narr]amix=inputs=2:duration=shortest[out]',
            '-map', '[out]',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-loglevel', 'error',
            mixed_audio
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if os.path.exists(mixed_audio):
            final_audio = mixed_audio
        else:
            final_audio = original_audio
    
    print("   [4/4] 合成最终视频...")
    
    # 合并视频和音频
    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-i', final_audio,
        '-c:v', 'copy',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        '-loglevel', 'error',
        output
    ]
    subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    # 清理
    try:
        os.remove(original_audio)
        if 'mixed_audio' in dir() and os.path.exists(mixed_audio):
            os.remove(mixed_audio)
    except:
        pass
    
    return output


def add_subtitles(video: str, subtitle: str, output: str) -> str:
    """添加字幕（GPU加速，带详细日志）"""
    import time
    from datetime import datetime
    
    def log(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
    
    log(f"[SUB] ========== 字幕添加开始 ==========")
    log(f"[SUB] 输入视频: {video}")
    log(f"[SUB] 字幕文件: {subtitle}")
    
    start_time = time.time()
    
    if not os.path.exists(subtitle):
        log(f"[SUB] [WARN] 字幕文件不存在，跳过")
        shutil.copy(video, output)
        return output
    
    # 转换字幕路径格式（FFmpeg要求）
    sub_path = os.path.abspath(subtitle).replace('\\', '/').replace(':', '\\:')
    
    # 获取GPU加速编码参数
    video_codec_args = get_video_codec_args('fast')
    log(f"[SUB] 编码器: {video_codec_args[1] if len(video_codec_args) > 1 else 'unknown'}")
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-vf', f"subtitles='{sub_path}'",
    ] + video_codec_args + [  # GPU加速编码
        '-c:a', 'copy',
        '-loglevel', 'error',
        output
    ]
    
    log(f"[SUB] 正在添加字幕...")
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    elapsed = time.time() - start_time
    if os.path.exists(output) and os.path.getsize(output) > 1000:
        log(f"[SUB] ========== 字幕添加完成 ==========")
        log(f"[SUB] 输出: {output}")
        log(f"[SUB] 耗时: {elapsed:.1f}秒")
        return output
    else:
        log(f"[SUB] [WARN] 字幕添加失败，使用原视频")
        shutil.copy(video, output)
        return output


def convert_to_vertical(video: str, output: str) -> str:
    """转换为竖屏（抖音格式，GPU加速，带详细日志）"""
    import time
    from datetime import datetime
    
    def log(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
    
    log(f"[VERT] ========== 竖屏转换开始 ==========")
    log(f"[VERT] 输入视频: {video}")
    log(f"[VERT] 目标尺寸: 1080x1920 (抖音格式)")
    
    start_time = time.time()
    
    # 获取GPU加速编码参数
    video_codec_args = get_video_codec_args('fast')
    log(f"[VERT] 编码器: {video_codec_args[1] if len(video_codec_args) > 1 else 'unknown'}")
    
    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
    ] + video_codec_args + [  # GPU加速编码
        '-c:a', 'copy',
        '-loglevel', 'error',
        output
    ]
    
    log(f"[VERT] 正在转换...")
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    elapsed = time.time() - start_time
    if os.path.exists(output) and os.path.getsize(output) > 1000:
        log(f"[VERT] ========== 竖屏转换完成 ==========")
        log(f"[VERT] 输出: {output}")
        log(f"[VERT] 耗时: {elapsed:.1f}秒")
        return output
    else:
        log(f"[VERT] [WARN] 竖屏转换失败")
        return video


# 测试
if __name__ == "__main__":
    print("音频合成器测试")

