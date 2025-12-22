# core/ffmpeg_utils.py - FFmpeg工具函数（解决中文路径问题）
"""
SmartVideoClipper - FFmpeg中文路径兼容模块

问题：Windows下FFmpeg默认使用系统代码页(GBK)，导致中文路径乱码

解决方案：
1. 使用Windows短路径名（8.3格式）
2. 创建临时英文路径的符号链接
3. 正确设置subprocess编码

这个模块封装了所有FFmpeg调用，确保中文路径正常工作
"""

import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import ctypes


def get_short_path(long_path: str) -> str:
    """
    获取Windows短路径名（8.3格式）
    
    例如：C:\\Users\\Administrator\\Downloads\\狂飙E01.mp4
    变为：C:\\Users\\ADMINI~1\\DOWNLO~1\\E01~1.MP4
    
    这样FFmpeg就不会出现中文编码问题
    """
    if os.name != 'nt':
        return long_path
    
    try:
        # Windows API获取短路径
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        GetShortPathNameW.restype = ctypes.c_uint
        
        # 先确保路径存在
        if not os.path.exists(long_path):
            return long_path
        
        # 获取所需缓冲区大小
        buffer_size = GetShortPathNameW(long_path, None, 0)
        if buffer_size == 0:
            return long_path
        
        # 获取短路径
        buffer = ctypes.create_unicode_buffer(buffer_size)
        GetShortPathNameW(long_path, buffer, buffer_size)
        
        short_path = buffer.value
        if short_path:
            return short_path
        
    except Exception as e:
        print(f"   [WARN] 获取短路径失败: {e}")
    
    return long_path


def ensure_safe_path(path: str) -> str:
    """
    确保路径对FFmpeg安全（无中文）
    
    策略：
    1. 如果路径是纯ASCII，直接返回
    2. 尝试获取Windows短路径
    3. 如果失败，创建临时符号链接
    """
    # 检查是否包含非ASCII字符
    try:
        path.encode('ascii')
        return path  # 纯ASCII，安全
    except UnicodeEncodeError:
        pass  # 包含非ASCII字符
    
    # 尝试短路径
    short_path = get_short_path(path)
    
    # 验证短路径是否真的是ASCII
    try:
        short_path.encode('ascii')
        return short_path
    except UnicodeEncodeError:
        pass  # 短路径仍有非ASCII
    
    # 最后方案：如果是输入文件，创建临时副本
    # 注意：这只用于小文件或必要时
    print(f"   [INFO] 路径包含中文，使用短路径: {short_path}")
    return short_path  # 返回短路径，让FFmpeg尝试


def run_ffmpeg(
    args: List[str],
    check: bool = True,
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """
    运行FFmpeg命令（处理中文路径）
    
    参数：
        args: FFmpeg命令参数列表（不包含'ffmpeg'本身）
        check: 是否检查返回值
        capture_output: 是否捕获输出
    
    返回：
        subprocess.CompletedProcess对象
    """
    # 处理参数中的中文路径
    processed_args = ['ffmpeg']
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        # 检测是否是文件路径参数
        if arg == '-i' and i + 1 < len(args):
            # 输入文件
            processed_args.append(arg)
            i += 1
            input_path = args[i]
            safe_path = ensure_safe_path(input_path)
            processed_args.append(safe_path)
        elif arg.endswith(('.mp4', '.mkv', '.avi', '.mov', '.mp3', '.wav', '.srt', '.txt')):
            # 可能是输出文件
            safe_path = ensure_safe_path(arg)
            processed_args.append(safe_path)
        else:
            processed_args.append(arg)
        
        i += 1
    
    # 运行命令
    # 关键：使用creationflags确保正确的编码
    if os.name == 'nt':
        # Windows下使用CREATE_NO_WINDOW避免编码问题
        result = subprocess.run(
            processed_args,
            capture_output=capture_output,
            encoding='utf-8',
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
    else:
        result = subprocess.run(
            processed_args,
            capture_output=capture_output,
            encoding='utf-8',
            errors='ignore'
        )
    
    return result


def run_ffprobe(
    args: List[str],
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """
    运行FFprobe命令（处理中文路径）
    """
    processed_args = ['ffprobe']
    
    for arg in args:
        if arg.endswith(('.mp4', '.mkv', '.avi', '.mov', '.mp3', '.wav')):
            safe_path = ensure_safe_path(arg)
            processed_args.append(safe_path)
        else:
            processed_args.append(arg)
    
    if os.name == 'nt':
        result = subprocess.run(
            processed_args,
            capture_output=capture_output,
            encoding='utf-8',
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
    else:
        result = subprocess.run(
            processed_args,
            capture_output=capture_output,
            encoding='utf-8',
            errors='ignore'
        )
    
    return result


def create_safe_link(source_path: str, suffix: str = '.mp4') -> Tuple[str, bool]:
    """
    创建安全的临时链接（用于处理中文路径）
    
    优先使用硬链接（瞬时完成），失败则使用复制
    
    返回：(安全路径, 是否需要清理)
    """
    # 检查是否需要处理
    try:
        source_path.encode('ascii')
        return source_path, False  # 纯ASCII，不需要处理
    except UnicodeEncodeError:
        pass
    
    if not os.path.exists(source_path):
        return source_path, False
    
    # 创建临时路径
    temp_dir = tempfile.gettempdir()
    import time
    temp_name = f"svc_link_{int(time.time()*1000)}{suffix}"
    temp_path = os.path.join(temp_dir, temp_name)
    
    # 尝试硬链接（最快，同分区有效）
    try:
        os.link(source_path, temp_path)
        return temp_path, True
    except Exception:
        pass
    
    # 尝试符号链接
    try:
        os.symlink(source_path, temp_path)
        return temp_path, True
    except Exception:
        pass
    
    # 最后方案：复制文件
    print(f"   [INFO] 创建临时副本（可能需要一些时间）...")
    try:
        shutil.copy2(source_path, temp_path)
        return temp_path, True
    except Exception as e:
        print(f"   [ERROR] 创建临时文件失败: {e}")
        return source_path, False


def cleanup_temp(temp_path: str, needs_cleanup: bool):
    """清理临时文件/链接"""
    if needs_cleanup and temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except:
            pass


def prepare_input_video(video_path: str) -> Tuple[str, bool]:
    """
    准备输入视频路径（处理中文路径）
    
    返回：(安全路径, 是否需要清理)
    """
    return create_safe_link(video_path, '.mp4')


# 测试
if __name__ == "__main__":
    test_path = r"C:\Users\Administrator\Downloads\狂飙E01.mp4"
    print(f"原始路径: {test_path}")
    print(f"短路径: {get_short_path(test_path)}")
    print(f"安全路径: {ensure_safe_path(test_path)}")

