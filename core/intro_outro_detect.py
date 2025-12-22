# core/intro_outro_detect.py - 片头片尾检测与去除
"""
SmartVideoClipper - 片头片尾检测模块

功能: 自动检测并去除视频的片头（logo、黑屏）和片尾（演职员表、黑屏）
用途: 在处理前先清理无用片段，提高剪辑质量

依赖: opencv-python, numpy, ffmpeg
"""

import cv2
import numpy as np
import subprocess
import os
from typing import Tuple, Optional


def get_video_duration(video_path: str) -> float:
    """获取视频总时长（秒）"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        # 使用OpenCV作为备选
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        return frame_count / fps if fps > 0 else 0


def analyze_frame_brightness(frame: np.ndarray) -> float:
    """分析帧的平均亮度（0-255）"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)


def analyze_frame_variance(frame: np.ndarray) -> float:
    """分析帧的方差（用于检测纯色/黑屏）"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.var(gray)


def detect_intro_outro(
    video_path: str,
    max_intro_duration: float = 120.0,  # 最长片头时间（秒）
    max_outro_duration: float = 180.0,  # 最长片尾时间（秒）
    black_threshold: float = 15.0,       # 黑屏亮度阈值
    variance_threshold: float = 100.0,   # 纯色方差阈值
    sample_interval: float = 1.0         # 采样间隔（秒）
) -> Tuple[float, float]:
    """
    检测视频的片头和片尾时间点
    
    检测策略：
    1. 黑屏检测：连续黑屏帧
    2. 静态画面检测：低方差帧（logo、字幕卡）
    3. 场景变化检测：找到第一个明显场景变化点
    
    参数:
        video_path: 视频路径
        max_intro_duration: 最大片头时长
        max_outro_duration: 最大片尾时长
        black_threshold: 黑屏亮度阈值
        variance_threshold: 纯色方差阈值
        sample_interval: 采样间隔
    
    返回:
        (intro_end, outro_start): 片头结束时间, 片尾开始时间
    """
    print(f"[DETECT] 正在检测片头片尾...")
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    if duration == 0:
        cap.release()
        return 0, duration
    
    # ===== 检测片头 =====
    intro_end = 0
    last_black_end = 0
    frame_interval = int(fps * sample_interval)
    
    # 分析片头区域
    intro_frames = int(min(max_intro_duration * fps, total_frames * 0.3))  # 最多分析前30%
    prev_frame = None
    significant_change_found = False
    
    for frame_idx in range(0, intro_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time = frame_idx / fps
        brightness = analyze_frame_brightness(frame)
        variance = analyze_frame_variance(frame)
        
        # 检测黑屏
        if brightness < black_threshold:
            last_black_end = current_time + sample_interval
            continue
        
        # 检测低方差（可能是logo、字幕卡）
        if variance < variance_threshold:
            last_black_end = current_time + sample_interval
            continue
        
        # 检测场景变化
        if prev_frame is not None:
            diff = cv2.absdiff(frame, prev_frame)
            change = np.mean(diff)
            if change > 30:  # 显著变化
                if not significant_change_found:
                    significant_change_found = True
                    # 第一次显著变化可能是从片头到正片
                    intro_end = max(last_black_end, current_time - sample_interval)
                    break
        
        prev_frame = frame.copy()
    
    # 如果没有检测到明显片头，使用最后一个黑屏/静态画面时间
    if intro_end == 0:
        intro_end = last_black_end
    
    # ===== 检测片尾 =====
    outro_start = duration
    last_content_time = duration
    
    # 从视频末尾向前分析
    outro_start_frame = max(0, total_frames - int(max_outro_duration * fps))
    outro_start_frame = max(outro_start_frame, int(total_frames * 0.7))  # 至少从70%开始
    
    # 收集片尾区域的帧信息
    outro_frames_data = []
    for frame_idx in range(total_frames - 1, outro_start_frame, -frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        current_time = frame_idx / fps
        brightness = analyze_frame_brightness(frame)
        variance = analyze_frame_variance(frame)
        
        outro_frames_data.append({
            'time': current_time,
            'brightness': brightness,
            'variance': variance,
            'is_black': brightness < black_threshold,
            'is_static': variance < variance_threshold * 2  # 片尾字幕容差更大
        })
    
    # 从后向前找第一个正常内容帧
    continuous_end_frames = 0
    for data in outro_frames_data:
        if data['is_black'] or data['is_static']:
            continuous_end_frames += 1
        else:
            # 找到正常内容
            if continuous_end_frames >= 3:  # 连续3个异常帧才认为是片尾
                outro_start = data['time'] + sample_interval
            break
    
    cap.release()
    
    # 安全边界检查
    intro_end = max(0, min(intro_end, duration * 0.3))  # 片头不超过30%
    outro_start = max(duration * 0.7, min(outro_start, duration))  # 片尾不早于70%
    
    # 确保有效内容时长
    if outro_start - intro_end < 60:  # 如果有效内容少于60秒，可能检测有误
        print("   [WARNING] 检测到的有效内容过短，重置为全片")
        intro_end = 0
        outro_start = duration
    
    print(f"   片头结束: {intro_end:.1f}秒")
    print(f"   片尾开始: {outro_start:.1f}秒")
    print(f"   有效内容: {intro_end:.1f}秒 - {outro_start:.1f}秒 ({outro_start - intro_end:.1f}秒)")
    
    return intro_end, outro_start


def trim_video(
    video_path: str,
    output_path: str,
    start_time: float,
    end_time: float
) -> str:
    """
    裁剪视频，去除片头片尾
    
    参数:
        video_path: 输入视频
        output_path: 输出视频
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
    
    返回:
        输出文件路径
    """
    print(f"[TRIM] 裁剪视频: {start_time:.1f}s - {end_time:.1f}s")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    duration = end_time - start_time
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', video_path,
        '-t', str(duration),
        '-c', 'copy',  # 直接复制，不重新编码（更快）
        '-avoid_negative_ts', 'make_zero',
        '-loglevel', 'error',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # 如果copy模式失败，尝试重新编码
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        print("   [INFO] 快速裁剪失败，尝试重新编码...")
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', video_path,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-loglevel', 'error',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"[OK] 视频裁剪完成: {output_path}")
        return output_path
    else:
        raise RuntimeError(f"[ERROR] 视频裁剪失败: {result.stderr[:200] if result.stderr else 'unknown'}")


def auto_trim_intro_outro(
    video_path: str,
    output_path: str,
    skip_if_short: float = 300.0  # 少于5分钟的视频跳过检测
) -> Tuple[str, float, float]:
    """
    自动检测并去除片头片尾（一体化函数）
    
    参数:
        video_path: 输入视频
        output_path: 输出视频
        skip_if_short: 短视频跳过阈值（秒）
    
    返回:
        (output_path, intro_end, outro_start)
    """
    duration = get_video_duration(video_path)
    
    # 短视频跳过检测
    if duration < skip_if_short:
        print(f"[SKIP] 视频较短({duration:.0f}秒)，跳过片头片尾检测")
        return video_path, 0, duration
    
    # 检测片头片尾
    intro_end, outro_start = detect_intro_outro(video_path)
    
    # 如果检测到需要裁剪
    if intro_end > 5 or (duration - outro_start) > 5:  # 至少5秒才裁剪
        trimmed_path = trim_video(video_path, output_path, intro_end, outro_start)
        return trimmed_path, intro_end, outro_start
    else:
        print("[SKIP] 未检测到明显片头片尾，使用原视频")
        return video_path, 0, duration


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
        if os.path.exists(test_video):
            print(f"测试视频: {test_video}")
            print("=" * 50)
            
            # 检测
            intro_end, outro_start = detect_intro_outro(test_video)
            
            # 裁剪测试
            output = test_video.replace('.mp4', '_trimmed.mp4')
            trim_video(test_video, output, intro_end, outro_start)
        else:
            print(f"视频不存在: {test_video}")
    else:
        print("用法: python intro_outro_detect.py video.mp4")

