# core/intro_outro_detect.py - 片头片尾检测与去除（增强版）
"""
SmartVideoClipper - 片头片尾检测模块 v2.0

多维度检测方法：
1. 视觉检测：黑屏、静态画面、logo
2. 音频检测：片头曲特征（音乐vs对话）
3. 规则检测：国标规定片头≤90秒，片尾≤180秒

参考标准：
- 国家广播电视总局《电视剧母版制作规范》
- 片头时长不超过90秒
- 片尾时长不超过180秒
- 正片时长不少于41分钟
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
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        return frame_count / fps if fps > 0 else 0


def analyze_audio_type(video_path: str, start: float, duration: float = 5.0) -> dict:
    """
    分析指定时间段的音频类型
    
    返回:
        - has_speech: 是否有人声对话
        - has_music: 是否有背景音乐
        - is_silent: 是否静音
    """
    try:
        # 使用ffmpeg分析音频
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', video_path,
            '-t', str(duration),
            '-af', 'volumedetect',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        # 解析音量
        mean_volume = -60
        max_volume = -60
        for line in result.stderr.split('\n'):
            if 'mean_volume' in line:
                try:
                    mean_volume = float(line.split(':')[1].strip().replace(' dB', ''))
                except:
                    pass
            if 'max_volume' in line:
                try:
                    max_volume = float(line.split(':')[1].strip().replace(' dB', ''))
                except:
                    pass
        
        # 判断音频类型
        is_silent = mean_volume < -50
        has_audio = mean_volume > -40
        
        # 音乐通常音量稳定，对话音量波动大
        volume_range = max_volume - mean_volume
        likely_music = has_audio and volume_range < 15  # 音乐音量波动小
        likely_speech = has_audio and volume_range > 15  # 对话音量波动大
        
        return {
            'mean_volume': mean_volume,
            'max_volume': max_volume,
            'is_silent': is_silent,
            'likely_music': likely_music,
            'likely_speech': likely_speech
        }
    except:
        return {
            'mean_volume': -60,
            'max_volume': -60,
            'is_silent': True,
            'likely_music': False,
            'likely_speech': False
        }


def analyze_frame_content(frame: np.ndarray) -> dict:
    """分析帧内容特征"""
    if frame is None:
        return {'is_black': True, 'is_static': True, 'brightness': 0, 'variance': 0}
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    variance = np.var(gray)
    
    # 边缘检测（logo和字幕通常有清晰边缘）
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.mean(edges) / 255
    
    return {
        'is_black': brightness < 20,
        'is_static': variance < 200,
        'brightness': brightness,
        'variance': variance,
        'edge_density': edge_density,
        'has_text_like': edge_density > 0.05 and variance < 1000  # 可能有字幕/logo
    }


def detect_intro_enhanced(video_path: str, max_duration: float = 120.0) -> float:
    """
    增强版片头检测
    
    检测策略：
    1. 前120秒内，找到"音乐→对话"的转换点
    2. 如果有明显的黑屏或静态画面，以此为边界
    3. 参考国标：片头不超过90秒
    
    返回：
        片头结束时间（秒）
    """
    print("[INTRO] 检测片头...")
    
    if not os.path.exists(video_path):
        return 0
    
    total_duration = get_video_duration(video_path)
    if total_duration == 0:
        return 0
    
    # 限制检测范围
    check_duration = min(max_duration, total_duration * 0.15)  # 最多检测前15%
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    
    # 每3秒采样分析
    interval = 3.0
    analysis_results = []
    
    for t in np.arange(0, check_duration, interval):
        # 视觉分析
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        
        visual = analyze_frame_content(frame if ret else None)
        
        # 音频分析
        audio = analyze_audio_type(video_path, t, interval)
        
        analysis_results.append({
            'time': t,
            'visual': visual,
            'audio': audio
        })
        
        # 打印分析过程
        status = []
        if visual['is_black']:
            status.append('黑屏')
        if visual['has_text_like']:
            status.append('字幕/Logo')
        if audio['likely_music']:
            status.append('音乐')
        if audio['likely_speech']:
            status.append('对话')
        if audio['is_silent']:
            status.append('静音')
        
        print(f"   {t:.0f}s: {', '.join(status) if status else '正常画面'}")
    
    cap.release()
    
    # 寻找片头结束点
    intro_end = 0
    
    # 策略1：找到第一个明显的对话开始点
    for i, r in enumerate(analysis_results):
        if r['audio']['likely_speech'] and not r['visual']['is_black']:
            # 找到对话，回退一个间隔作为片头结束
            intro_end = max(0, r['time'] - interval)
            print(f"   [策略1] 检测到对话开始于 {r['time']:.0f}s，片头结束于 {intro_end:.0f}s")
            break
    
    # 策略2：如果前面全是音乐，找音乐结束点
    if intro_end == 0:
        music_end = 0
        for r in analysis_results:
            if r['audio']['likely_music']:
                music_end = r['time'] + interval
            elif music_end > 0 and not r['audio']['likely_music']:
                intro_end = music_end
                print(f"   [策略2] 音乐结束于 {intro_end:.0f}s")
                break
    
    # 策略3：找黑屏后的第一个正常画面
    if intro_end == 0:
        for i, r in enumerate(analysis_results):
            if r['visual']['is_black'] and i + 1 < len(analysis_results):
                next_r = analysis_results[i + 1]
                if not next_r['visual']['is_black']:
                    intro_end = next_r['time']
                    print(f"   [策略3] 黑屏结束于 {intro_end:.0f}s")
                    break
    
    # 限制：片头不超过90秒（国标）
    if intro_end > 90:
        print(f"   [限制] 片头超过90秒，按90秒处理")
        intro_end = 90
    
    print(f"   片头时长: {intro_end:.0f}秒")
    return intro_end


def detect_outro_enhanced(video_path: str, max_duration: float = 180.0) -> float:
    """
    增强版片尾检测
    
    检测策略：
    1. 从结尾向前，找到"对话→音乐/黑屏"的转换点
    2. 检测演职员表特征（滚动文字）
    3. 参考国标：片尾不超过180秒
    
    返回：
        片尾开始时间（秒）
    """
    print("[OUTRO] 检测片尾...")
    
    if not os.path.exists(video_path):
        return float('inf')
    
    total_duration = get_video_duration(video_path)
    if total_duration == 0:
        return float('inf')
    
    # 限制检测范围
    check_duration = min(max_duration, total_duration * 0.15)
    start_check = total_duration - check_duration
    
    cap = cv2.VideoCapture(video_path)
    
    # 每3秒采样分析
    interval = 3.0
    analysis_results = []
    
    for t in np.arange(start_check, total_duration, interval):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        
        visual = analyze_frame_content(frame if ret else None)
        audio = analyze_audio_type(video_path, t, interval)
        
        analysis_results.append({
            'time': t,
            'visual': visual,
            'audio': audio
        })
    
    cap.release()
    
    # 从后向前寻找片尾开始点
    outro_start = total_duration
    
    # 策略1：找到最后一段对话的结束点
    last_speech_time = total_duration
    for r in reversed(analysis_results):
        if r['audio']['likely_speech'] and not r['visual']['is_black']:
            last_speech_time = r['time'] + interval
            break
    
    if last_speech_time < total_duration - 10:
        outro_start = last_speech_time
        print(f"   [策略1] 最后对话结束于 {outro_start:.0f}s")
    
    # 策略2：检测连续的黑屏或静态画面
    static_start = None
    for r in analysis_results:
        if r['visual']['is_black'] or (r['audio']['likely_music'] and r['visual']['has_text_like']):
            if static_start is None:
                static_start = r['time']
        else:
            static_start = None
    
    if static_start and static_start < outro_start:
        outro_start = static_start
        print(f"   [策略2] 片尾画面开始于 {outro_start:.0f}s")
    
    # 限制：确保正片至少有一定时长
    min_content_duration = total_duration * 0.7  # 正片至少占70%
    if outro_start < min_content_duration:
        outro_start = min_content_duration
        print(f"   [限制] 确保正片时长，片尾开始于 {outro_start:.0f}s")
    
    print(f"   片尾时长: {total_duration - outro_start:.0f}秒")
    return outro_start


def trim_video(
    video_path: str,
    output_path: str,
    start_time: float,
    end_time: float
) -> str:
    """裁剪视频"""
    print(f"[TRIM] 裁剪视频: {start_time:.1f}s - {end_time:.1f}s")
    
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    duration = end_time - start_time
    
    # 快速裁剪（不重新编码）
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', video_path,
        '-t', str(duration),
        '-c', 'copy',
        '-avoid_negative_ts', 'make_zero',
        '-loglevel', 'error',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        print("   快速裁剪失败，尝试重新编码...")
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
        raise RuntimeError(f"[ERROR] 视频裁剪失败")


def auto_trim_intro_outro(
    video_path: str,
    output_path: str,
    skip_if_short: float = 300.0
) -> Tuple[str, float, float]:
    """
    自动检测并去除片头片尾
    
    返回:
        (output_path, intro_end, outro_start)
    """
    duration = get_video_duration(video_path)
    
    if duration < skip_if_short:
        print(f"[SKIP] 视频较短({duration:.0f}秒)，跳过片头片尾检测")
        return video_path, 0, duration
    
    # 检测片头
    intro_end = detect_intro_enhanced(video_path)
    
    # 检测片尾
    outro_start = detect_outro_enhanced(video_path)
    
    # 确保有效内容时长合理
    content_duration = outro_start - intro_end
    if content_duration < duration * 0.5:
        print(f"[WARNING] 检测结果异常（内容仅{content_duration:.0f}秒），使用保守值")
        intro_end = min(intro_end, 60)  # 最多去60秒片头
        outro_start = max(outro_start, duration - 120)  # 最多去120秒片尾
    
    # 判断是否需要裁剪
    if intro_end > 5 or (duration - outro_start) > 5:
        print(f"\n[RESULT] 片头: 0-{intro_end:.0f}秒, 片尾: {outro_start:.0f}-{duration:.0f}秒")
        print(f"[RESULT] 有效内容: {intro_end:.0f}秒 - {outro_start:.0f}秒 ({outro_start - intro_end:.0f}秒)")
        trimmed_path = trim_video(video_path, output_path, intro_end, outro_start)
        return trimmed_path, intro_end, outro_start
    else:
        print("[SKIP] 未检测到明显片头片尾")
        return video_path, 0, duration


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
        if os.path.exists(test_video):
            print(f"测试视频: {test_video}")
            print("=" * 50)
            
            intro_end = detect_intro_enhanced(test_video)
            outro_start = detect_outro_enhanced(test_video)
            
            duration = get_video_duration(test_video)
            print(f"\n总时长: {duration:.0f}秒")
            print(f"片头: 0-{intro_end:.0f}秒")
            print(f"片尾: {outro_start:.0f}-{duration:.0f}秒")
            print(f"正片: {intro_end:.0f}-{outro_start:.0f}秒 ({outro_start - intro_end:.0f}秒)")
        else:
            print(f"视频不存在: {test_video}")
    else:
        print("用法: python intro_outro_detect.py video.mp4")
