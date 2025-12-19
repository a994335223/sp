# core/smart_cut.py - 智能剪辑
"""
SmartVideoClipper - 智能剪辑模块

功能: 使用FFmpeg进行视频片段提取和拼接
用途: 从长视频中提取精华片段

依赖: ffmpeg (需要安装并添加到PATH)
"""

import subprocess
import os
import re


def get_video_encoder():
    """
    检测NVIDIA NVENC硬件加速支持
    
    💡 GTX 1080及以上显卡100%支持NVENC，应优先使用GPU加速！
    - h264_nvenc: GPU硬件编码（速度快5-10倍，几乎不占CPU）
    - libx264: CPU软件编码（仅作为极端情况的备选）
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True
        )
        if 'h264_nvenc' in result.stdout:
            print("🚀 检测到NVENC硬件编码支持，使用GPU加速！")
            return 'h264_nvenc'  # ⭐ 优先GPU加速
    except:
        pass
    print("⚠️ 未检测到NVENC，使用CPU编码（速度较慢）")
    return 'libx264'  # 仅作为极端fallback


# 全局编码器（启动时检测一次）
# ⭐ GTX 1080及以上默认使用GPU加速
VIDEO_ENCODER = get_video_encoder()


def extract_clips(video_path: str, clips: list, output_dir: str):
    """
    提取多个视频片段
    
    参数:
        video_path: 源视频
        clips: [{'start': 10, 'end': 20}, ...]
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for i, clip in enumerate(clips):
        output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")
        
        # 使用自动检测的编码器（GPU加速或CPU fallback）
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(clip['start']),
            '-i', video_path,
            '-t', str(clip['end'] - clip['start']),
            '-c:v', VIDEO_ENCODER,  # 🔧 自动选择: h264_nvenc 或 libx264
            '-preset', 'fast',
            '-c:a', 'aac',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True)
    
    print(f"✅ 已提取 {len(clips)} 个片段到 {output_dir}")


def concat_clips(clip_files: list, output_path: str):
    """
    拼接多个视频片段
    
    参数:
        clip_files: 视频文件路径列表
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 创建文件列表（使用UTF-8编码支持中文路径）
    list_file = "concat_list.txt"
    with open(list_file, 'w', encoding='utf-8') as f:
        for clip in clip_files:
            # 将路径转换为绝对路径，避免中文路径问题
            abs_path = os.path.abspath(clip)
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c:v', VIDEO_ENCODER,  # 🔧 自动选择编码器
        '-c:a', 'aac',
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True)
    
    # 清理临时文件
    if os.path.exists(list_file):
        os.remove(list_file)
    
    print(f"✅ 视频拼接完成: {output_path}")


def parse_keep_original_markers(script: str) -> list:
    """
    解析文案中的【保留原声】标记
    返回需要保留原声的时间段
    
    参数:
        script: 解说文案
    
    返回:
        [{'start': 10, 'end': 20}, ...]
    """
    # 支持多种格式的标记
    patterns = [
        r'【保留原声[：:]\s*(\d+)秒?[-~到至](\d+)秒?】',
        r'【原声[：:]\s*(\d+)秒?[-~到至](\d+)秒?】',
        r'\[保留原声[：:]\s*(\d+)[-~到至](\d+)\]',
        r'\[原声[：:]\s*(\d+)[-~到至](\d+)\]',
    ]
    
    results = []
    for pattern in patterns:
        matches = re.findall(pattern, script)
        results.extend(matches)
    
    return [{'start': int(m[0]), 'end': int(m[1])} for m in results]


def select_best_clips(scenes: list, target_duration: int = 240) -> list:
    """
    选取最佳片段，控制总时长
    
    参数:
        scenes: 分析后的镜头列表
        target_duration: 目标时长（秒），默认240秒=4分钟
    
    返回:
        选中的片段列表 [{'start': ..., 'end': ...}, ...]
    """
    # 按重要性排序
    sorted_scenes = sorted(scenes, key=lambda x: x.get('confidence', 0), reverse=True)
    
    selected = []
    total_duration = 0
    
    for scene in sorted_scenes:
        duration = scene['end'] - scene['start']
        if total_duration + duration <= target_duration:
            selected.append({
                'start': scene['start'],
                'end': scene['end']
            })
            total_duration += duration
    
    # 按时间顺序排序
    selected.sort(key=lambda x: x['start'])
    
    print(f"   选取了 {len(selected)} 个片段，总时长 {total_duration:.0f}秒")
    return selected


# 使用示例
if __name__ == "__main__":
    # 测试智能剪辑
    print(f"当前编码器: {VIDEO_ENCODER}")
    
    # 提取重要片段
    clips = [
        {'start': 120, 'end': 180},   # 2:00-3:00
        {'start': 600, 'end': 660},   # 10:00-11:00
        {'start': 3600, 'end': 3660}, # 1:00:00-1:01:00
    ]
    
    test_video = "test_video.mp4"
    if os.path.exists(test_video):
        extract_clips(test_video, clips, "clips/")
    else:
        print(f"⚠️ 测试视频不存在: {test_video}")
    
    # 测试解析保留原声标记
    test_script = """
    这部电影开场就很精彩。
    【保留原声：120秒-150秒】
    然后男主开始了他的表演。
    【原声:300-330】
    最后是感人的结局。
    """
    markers = parse_keep_original_markers(test_script)
    print(f"解析到的原声标记: {markers}")

