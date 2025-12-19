# core/scene_detect.py - 镜头切分
"""
SmartVideoClipper - 镜头切分模块

功能: 使用PySceneDetect检测视频中的镜头切换点
用途: 把2小时电影分成几百个镜头，便于后续分析

依赖: scenedetect[opencv]
"""

from scenedetect import detect, ContentDetector
from scenedetect.video_splitter import split_video_ffmpeg
import os


def detect_scenes(video_path: str, output_dir: str, threshold: float = 27.0):
    """
    检测视频镜头切换点
    
    参数:
        video_path: 视频路径
        output_dir: 输出目录
        threshold: 检测阈值（越小越敏感，推荐27-30）
    
    返回:
        scenes: [{'index': 0, 'start': 0.0, 'end': 5.0, 'duration': 5.0}, ...]
        scene_list: PySceneDetect原生场景列表
    """
    print(f"🎬 开始检测镜头: {video_path}")
    
    # 🔧 检查文件存在性
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"❌ 视频文件不存在: {video_path}")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 检测镜头
    try:
        scene_list = detect(video_path, ContentDetector(threshold=threshold))
    except Exception as e:
        print(f"⚠️ 镜头检测失败: {e}")
        # 返回整个视频作为单个场景
        scene_list = []
    
    print(f"✅ 检测到 {len(scene_list)} 个镜头")
    
    # 保存镜头信息
    scenes = []
    for i, scene in enumerate(scene_list):
        start_time = scene[0].get_seconds()
        end_time = scene[1].get_seconds()
        duration = end_time - start_time
        scenes.append({
            'index': i,
            'start': start_time,
            'end': end_time,
            'duration': duration
        })
        
        # 只打印前10个和后5个镜头信息
        if i < 10 or i >= len(scene_list) - 5:
            print(f"  镜头 {i+1}: {start_time:.1f}s - {end_time:.1f}s ({duration:.1f}s)")
        elif i == 10:
            print(f"  ... (省略 {len(scene_list) - 15} 个镜头)")
    
    return scenes, scene_list


def split_into_scenes(video_path: str, scene_list, output_dir: str):
    """
    把视频分割成多个镜头文件
    
    参数:
        video_path: 源视频路径
        scene_list: detect_scenes返回的场景列表
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    split_video_ffmpeg(video_path, scene_list, output_dir)
    print(f"✅ 镜头文件已保存到: {output_dir}")


# 使用示例
if __name__ == "__main__":
    # 测试镜头检测
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        scenes, scene_list = detect_scenes(test_video, "scenes/")
        print(f"\n总共检测到 {len(scenes)} 个镜头")
        
        # 可选：分割成独立文件
        # split_into_scenes(test_video, scene_list, "scenes/")
    else:
        print(f"⚠️ 测试视频不存在: {test_video}")
        print("请提供一个视频文件进行测试")

