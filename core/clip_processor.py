# core/clip_processor.py - 片段处理器 v5.0 (GPU加速版)
"""
SmartVideoClipper - 片段级音频处理

核心原则：
每个片段独立处理音频，不是全程混音！

原声片段：保留原始音频
解说片段：替换为对应的TTS音频

GPU加速支持：
- NVIDIA NVENC (10倍速度提升)
- Intel QSV
- AMD AMF
- 自动fallback到CPU
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# 导入GPU编码器
try:
    from gpu_encoder import get_video_codec_args, is_hardware_available, get_encoder
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    def get_video_codec_args(quality='fast'):
        return ['-c:v', 'libx264', '-preset', 'fast']
    def is_hardware_available():
        return False


def extract_clip_with_audio_mode(
    source_video: str,
    start_time: float,
    end_time: float,
    output_path: str,
    audio_mode: str,
    narration_audio: str = None,
    narration_start: float = 0,
    narration_duration: float = None
) -> bool:
    """
    提取单个片段，根据audio_mode处理音频
    
    参数：
        source_video: 源视频
        start_time: 开始时间
        end_time: 结束时间
        output_path: 输出路径
        audio_mode: 'original' 或 'voiceover'
        narration_audio: 解说音频文件（仅voiceover模式需要）
        narration_start: 解说音频的起始位置
        narration_duration: 解说音频的持续时间
    
    返回：
        是否成功
    """
    duration = end_time - start_time
    
    # 获取GPU加速编码参数
    video_codec_args = get_video_codec_args('fast')
    
    if audio_mode == 'original':
        # 原声模式：直接提取，保留原始音频
        # 注意：统一编码参数，确保拼接时兼容
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', source_video,
            '-t', str(duration),
        ] + video_codec_args + [  # GPU加速编码
            '-c:a', 'aac',
            '-ar', '44100',      # 统一音频采样率
            '-ac', '2',          # 统一双声道
            '-loglevel', 'error',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
    elif audio_mode == 'voiceover' and narration_audio and os.path.exists(narration_audio):
        # 解说模式：提取视频，替换音频
        
        # 计算解说音频的使用范围
        if narration_duration is None:
            narration_duration = duration
        
        # 先提取视频（无音频）
        temp_video = output_path + '.temp.mp4'
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', source_video,
            '-t', str(duration),
        ] + video_codec_args + [  # GPU加速编码
            '-an',  # 无音频
            '-loglevel', 'error',
            temp_video
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if not os.path.exists(temp_video):
            return False
        
        # 提取对应时段的解说音频
        temp_audio = output_path + '.temp.wav'
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(narration_start),
            '-i', narration_audio,
            '-t', str(min(duration, narration_duration)),
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            '-loglevel', 'error',
            temp_audio
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        # 合并视频和解说音频
        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000:
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-i', temp_audio,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                '-loglevel', 'error',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        else:
            # 解说音频不可用，静音处理
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                '-loglevel', 'error',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        # 清理临时文件
        try:
            os.remove(temp_video)
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
        except:
            pass
    
    else:
        # 默认：保留原声
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', source_video,
            '-t', str(duration),
        ] + video_codec_args + [  # GPU加速编码
            '-c:a', 'aac',
            '-ar', '44100',
            '-ac', '2',
            '-loglevel', 'error',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def process_timeline_clips(
    source_video: str,
    timeline: List[Dict],
    narration_segments: List[Dict],
    output_dir: str
) -> Tuple[List[str], float]:
    """
    处理时间线上的所有片段
    
    参数：
        source_video: 源视频
        timeline: 时间线列表，每项包含 source_start, source_end, audio_mode, scene_id
        narration_segments: 解说音频片段列表，每项包含 audio_path, duration, scene_id
        output_dir: 输出目录
    
    返回：
        (片段文件列表, 总时长)
    """
    print("\n[CLIP] 分段处理片段...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    clip_files = []
    total_duration = 0
    
    original_count = 0
    voiceover_count = 0
    
    # 构建 scene_id -> 音频 的映射表（关键修复！）
    narration_map = {}
    for seg in narration_segments:
        scene_id = seg.get('scene_id')
        if scene_id is not None:
            narration_map[scene_id] = seg
    
    print(f"   TTS音频映射: {len(narration_map)}个")
    
    for i, item in enumerate(timeline):
        clip_path = os.path.join(output_dir, f"clip_{i:04d}.mp4")
        
        source_start = item['source_start']
        source_end = item['source_end']
        audio_mode = item.get('audio_mode', 'original')
        scene_id = item.get('scene_id')
        duration = source_end - source_start
        
        # 获取对应的解说音频（通过scene_id精确匹配！）
        narration_audio = None
        narration_start = 0
        narration_duration = None
        
        if audio_mode == 'voiceover':
            if scene_id in narration_map:
                seg = narration_map[scene_id]
                narration_audio = seg.get('audio_path')
                narration_start = seg.get('start', 0)
                narration_duration = seg.get('duration', duration)
            else:
                # 没有对应的TTS音频，改为使用原声
                print(f"   [WARN] 场景{scene_id}没有TTS音频，使用原声")
                audio_mode = 'original'
        
        # 提取片段
        success = extract_clip_with_audio_mode(
            source_video=source_video,
            start_time=source_start,
            end_time=source_end,
            output_path=clip_path,
            audio_mode=audio_mode,
            narration_audio=narration_audio,
            narration_start=narration_start,
            narration_duration=narration_duration
        )
        
        if success:
            clip_files.append(clip_path)
            total_duration += duration
            
            if audio_mode == 'original':
                original_count += 1
            else:
                voiceover_count += 1
        
        # 进度显示
        if (i + 1) % 10 == 0 or i == len(timeline) - 1:
            print(f"   进度: {i+1}/{len(timeline)} (🔊{original_count} 🎙️{voiceover_count})")
    
    print(f"[OK] 片段处理完成: {len(clip_files)}个, 总时长{total_duration:.0f}秒")
    print(f"     原声: {original_count}, 解说: {voiceover_count}")
    
    return clip_files, total_duration


def concat_processed_clips(
    clip_files: List[str],
    output_path: str
) -> bool:
    """
    拼接处理后的片段
    
    所有片段已经各自处理好音频，直接拼接即可
    """
    if not clip_files:
        return False
    
    print(f"\n[CONCAT] 拼接 {len(clip_files)} 个片段...")
    
    # 写入文件列表
    list_file = output_path + '.list.txt'
    with open(list_file, 'w', encoding='utf-8') as f:
        for clip in clip_files:
            abs_path = os.path.abspath(clip).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    
    # 拼接
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        '-loglevel', 'error',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    # 清理
    try:
        os.remove(list_file)
    except:
        pass
    
    success = os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    
    if success:
        size_mb = os.path.getsize(output_path) / (1024*1024)
        print(f"[OK] 拼接完成: {output_path} ({size_mb:.1f}MB)")
    else:
        print(f"[ERROR] 拼接失败")
    
    return success


# 测试
if __name__ == "__main__":
    print("片段处理器测试")
    
    # 测试extract_clip_with_audio_mode
    test_timeline = [
        {'source_start': 0, 'source_end': 10, 'audio_mode': 'original'},
        {'source_start': 10, 'source_end': 20, 'audio_mode': 'voiceover'},
        {'source_start': 20, 'source_end': 30, 'audio_mode': 'original'},
    ]
    print(f"测试时间线: {test_timeline}")

