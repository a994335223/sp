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
    """检测NVIDIA NVENC硬件加速支持"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        if 'h264_nvenc' in result.stdout:
            print("[GPU] 检测到NVENC硬件编码支持")
            return 'h264_nvenc'
    except:
        pass
    print("[CPU] 使用CPU编码")
    return 'libx264'


# 全局编码器
VIDEO_ENCODER = get_video_encoder()


def extract_single_clip(video_path: str, start: float, duration: float, output_path: str, use_gpu: bool = True):
    """
    提取单个视频片段，带备选方案
    
    返回: (success: bool, error_msg: str)
    """
    # 构建命令 - GPU 版本
    if use_gpu and VIDEO_ENCODER == 'h264_nvenc':
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', video_path,
            '-t', str(duration),
            '-c:v', 'h264_nvenc',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-loglevel', 'error',
            output_path
        ]
    else:
        # CPU 版本
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', video_path,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-loglevel', 'error',
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    # 检查结果
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        return True, ""
    else:
        return False, result.stderr[:200] if result.stderr else "unknown error"


def extract_clips(video_path: str, clips: list, output_dir: str):
    """
    提取多个视频片段
    
    参数:
        video_path: 源视频
        clips: [{'start': 10, 'end': 20}, ...]
        output_dir: 输出目录
    
    返回:
        生成的片段文件列表
    """
    # 检查输入视频
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"[ERROR] 源视频不存在: {video_path}")
    
    if not clips or len(clips) == 0:
        raise ValueError("[ERROR] 片段列表为空")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"   开始提取 {len(clips)} 个片段...")
    print(f"   源视频: {video_path}")
    print(f"   输出目录: {output_dir}")
    
    generated_files = []
    failed_clips = []
    
    # 首先尝试 GPU 编码
    use_gpu = (VIDEO_ENCODER == 'h264_nvenc')
    
    for i, clip in enumerate(clips):
        output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")
        
        # 计算时长
        start = clip.get('start', 0)
        end = clip.get('end', start + 10)
        duration = end - start
        
        if duration <= 0:
            print(f"   [SKIP] 片段 {i}: 时长无效 ({start}-{end})")
            continue
        
        # 尝试提取
        success, error = extract_single_clip(video_path, start, duration, output_path, use_gpu)
        
        if success:
            generated_files.append(output_path)
        else:
            # 如果 GPU 失败，尝试 CPU
            if use_gpu:
                success, error = extract_single_clip(video_path, start, duration, output_path, use_gpu=False)
                if success:
                    generated_files.append(output_path)
                    if i == 0:
                        print(f"   [INFO] GPU编码失败，切换到CPU编码")
                        use_gpu = False
                else:
                    failed_clips.append((i, error))
            else:
                failed_clips.append((i, error))
        
        # 进度显示（每10个显示一次）
        if (i + 1) % 10 == 0 or i == len(clips) - 1:
            print(f"   进度: {i + 1}/{len(clips)} ({len(generated_files)} 成功)")
    
    # 结果检查
    if len(generated_files) == 0:
        # 显示详细错误
        print(f"\n   [ERROR] 所有片段提取失败！")
        if failed_clips:
            print(f"   首个错误: {failed_clips[0][1]}")
        
        # 尝试诊断问题
        print(f"\n   诊断信息:")
        print(f"   - 视频路径: {video_path}")
        print(f"   - 视频存在: {os.path.exists(video_path)}")
        print(f"   - 视频大小: {os.path.getsize(video_path) if os.path.exists(video_path) else 'N/A'}")
        
        # 尝试用最简单的命令测试
        test_output = os.path.join(output_dir, "test_clip.mp4")
        test_cmd = ['ffmpeg', '-y', '-i', video_path, '-t', '5', '-c:v', 'libx264', '-c:a', 'aac', test_output]
        test_result = subprocess.run(test_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if os.path.exists(test_output) and os.path.getsize(test_output) > 0:
            print(f"   - 基础FFmpeg测试: 成功")
            os.remove(test_output)
        else:
            print(f"   - 基础FFmpeg测试: 失败")
            print(f"   - FFmpeg错误: {test_result.stderr[:300] if test_result.stderr else 'no error output'}")
        
        raise RuntimeError(f"[ERROR] 所有片段提取失败！共 {len(clips)} 个片段")
    
    if len(failed_clips) > 0:
        print(f"   [WARNING] {len(failed_clips)} 个片段提取失败")
    
    print(f"[OK] 已提取 {len(generated_files)}/{len(clips)} 个片段")
    return generated_files


def concat_clips(clip_files: list, output_path: str):
    """
    拼接多个视频片段
    """
    if not clip_files or len(clip_files) == 0:
        raise ValueError("[ERROR] 视频片段列表为空")
    
    # 过滤无效文件
    valid_files = [f for f in clip_files if os.path.exists(f) and os.path.getsize(f) > 1000]
    
    if len(valid_files) == 0:
        raise FileNotFoundError("[ERROR] 没有有效的视频片段文件")
    
    if len(valid_files) != len(clip_files):
        print(f"   [WARNING] {len(clip_files) - len(valid_files)} 个文件被跳过")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 创建文件列表
    list_file = os.path.join(output_dir if output_dir else ".", "concat_list.txt")
    with open(list_file, 'w', encoding='utf-8') as f:
        for clip in valid_files:
            # 使用正斜杠，避免 Windows 路径问题
            abs_path = os.path.abspath(clip).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    
    # 拼接命令 - 优先使用 copy 模式（更快）
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',  # 直接复制，不重新编码
        '-loglevel', 'error',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    # 如果 copy 模式失败，尝试重新编码
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        print("   [INFO] copy模式失败，尝试重新编码...")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-loglevel', 'error',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    # 清理
    if os.path.exists(list_file):
        os.remove(list_file)
    
    # 验证
    if not os.path.exists(output_path):
        raise RuntimeError(f"[ERROR] 视频拼接失败: {result.stderr[:200] if result.stderr else 'unknown'}")
    
    if os.path.getsize(output_path) < 1000:
        os.remove(output_path)
        raise RuntimeError("[ERROR] 视频拼接失败，输出文件过小")
    
    print(f"[OK] 视频拼接完成: {output_path}")
    return output_path


def parse_keep_original_markers(script: str) -> list:
    """解析文案中的【保留原声】标记"""
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
    """选取最佳片段"""
    if not scenes or len(scenes) == 0:
        return []
    
    sorted_scenes = sorted(scenes, key=lambda x: x.get('confidence', 0), reverse=True)
    
    selected = []
    total_duration = 0
    
    for scene in sorted_scenes:
        if 'start' not in scene or 'end' not in scene:
            continue
        
        duration = scene['end'] - scene['start']
        if duration <= 0 or duration > 300:
            continue
        
        if total_duration + duration <= target_duration:
            selected.append({
                'start': scene['start'],
                'end': scene['end']
            })
            total_duration += duration
    
    selected.sort(key=lambda x: x['start'])
    print(f"   选取了 {len(selected)} 个片段，总时长 {total_duration:.0f}秒")
    return selected


if __name__ == "__main__":
    print(f"当前编码器: {VIDEO_ENCODER}")
