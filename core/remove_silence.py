# core/remove_silence.py - 静音剪除
"""
SmartVideoClipper - 静音剪除模块

功能: 使用Auto-Editor自动去除视频中的静音片段
用途: 让视频节奏更紧凑

依赖: auto-editor
"""

import subprocess
import os


def remove_silence(
    input_path: str, 
    output_path: str,
    margin: str = "0.1sec",      # 保留边缘
    min_clip: float = 0.3,       # 最小片段长度
    min_cut: float = 0.2,        # 最小剪切长度
    silent_threshold: float = 0.04  # 静音阈值
):
    """
    自动去除视频中的静音片段
    
    参数:
        input_path: 输入视频
        output_path: 输出视频
        margin: 保留的边缘时间
        min_clip: 最小保留片段
        min_cut: 最小剪切片段
        silent_threshold: 静音阈值（0-1）
    
    返回:
        output_path: 输出文件路径
    """
    print(f"🔇 开始去除静音片段: {input_path}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        'auto-editor', input_path,
        '--margin', margin,
        '--min-clip-length', str(min_clip),
        '--min-cut-length', str(min_cut),
        '--silent-threshold', str(silent_threshold),
        '--no-open',  # 不自动打开
        '-o', output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        # 计算压缩比
        if os.path.exists(input_path) and os.path.exists(output_path):
            original_size = os.path.getsize(input_path)
            new_size = os.path.getsize(output_path)
            ratio = (1 - new_size / original_size) * 100
            print(f"✅ 静音剪除完成，视频缩短了约 {ratio:.1f}%")
        else:
            print(f"✅ 静音剪除完成")
    else:
        print(f"❌ 错误: {result.stderr}")
    
    return output_path


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
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
        return 0


# 使用示例
if __name__ == "__main__":
    # 测试静音剪除
    test_video = "test_video.mp4"
    output_video = "test_video_no_silence.mp4"
    
    if os.path.exists(test_video):
        # 获取原始时长
        original_duration = get_video_duration(test_video)
        print(f"原始视频时长: {original_duration:.1f}秒")
        
        # 执行静音剪除
        remove_silence(test_video, output_video)
        
        # 获取新时长
        new_duration = get_video_duration(output_video)
        print(f"处理后时长: {new_duration:.1f}秒")
        print(f"节省了: {original_duration - new_duration:.1f}秒")
    else:
        print(f"⚠️ 测试视频不存在: {test_video}")

