# core/cover_generator.py - 用Chinese-CLIP找出最吸引人的一帧作为封面
"""
SmartVideoClipper - 封面自动生成模块

功能: 使用Chinese-CLIP自动选择最佳封面帧
用途: 生成吸引眼球的视频封面

依赖: cn-clip, torch, opencv-python, pillow
"""

import cv2
from PIL import Image
import numpy as np
import os
import torch

# 🔧 使用Chinese-CLIP（国内版）
CLIP_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

try:
    import cn_clip.clip as clip
    from cn_clip.clip import load_from_name
    # 🔧 重命名变量，避免与环境变量CLIP_MODEL冲突
    _clip_model, _clip_preprocess = load_from_name("ViT-B-16", device=CLIP_DEVICE, download_root='./models')
except ImportError:
    print("⚠️ Chinese-CLIP未安装，封面生成功能不可用")
    _clip_model = None
    _clip_preprocess = None


def extract_keyframes(video_path: str, num_frames: int = 50) -> list:
    """
    提取视频关键帧
    
    参数:
        video_path: 视频路径
        num_frames: 提取帧数
    
    返回:
        帧列表 (OpenCV格式，BGR)
    """
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(total_frames // num_frames, 1)
    
    frames = []
    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
        if len(frames) >= num_frames:
            break
    
    cap.release()
    return frames


def auto_generate_cover(video_path: str, output_path: str):
    """
    自动生成视频封面
    使用CLIP找出最吸引人的一帧
    
    参数:
        video_path: 视频路径
        output_path: 封面输出路径
    """
    if _clip_model is None:
        print("⚠️ CLIP模型未加载，无法生成封面")
        return None
    
    print("🖼️ 自动生成封面...")
    
    # 提取关键帧
    frames = extract_keyframes(video_path, num_frames=50)
    
    if not frames:
        print("⚠️ 无法提取视频帧")
        return None
    
    # 定义"好封面"的特征
    prompts = [
        "精彩的电影场景",
        "戏剧性的一幕",
        "感人的场景",
        "美丽的电影画面",
        "令人印象深刻的镜头"
    ]
    
    # 预计算文本特征
    text_tokens = clip.tokenize(prompts).to(CLIP_DEVICE)
    with torch.no_grad():
        text_features = _clip_model.encode_text(text_tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)
    
    best_frame, best_score = None, 0
    for frame in frames:
        # 处理图像
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image_input = _clip_preprocess(image).unsqueeze(0).to(CLIP_DEVICE)
        
        with torch.no_grad():
            image_features = _clip_model.encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            score = (image_features @ text_features.T).mean().item()
        
        if score > best_score:
            best_frame, best_score = frame, score
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 保存封面图片
    if best_frame is not None:
        success = cv2.imwrite(output_path, best_frame)
        if success:
            print(f"✅ 封面已保存: {output_path} (得分: {best_score:.3f})")
            return output_path
        else:
            print(f"⚠️ 封面保存失败: {output_path}")
            return None
    
    return None


def add_title_to_cover(cover_path: str, title: str, output_path: str = None):
    """
    在封面上添加标题文字
    
    参数:
        cover_path: 封面图片路径
        title: 标题文字
        output_path: 输出路径（默认覆盖原文件）
    """
    if output_path is None:
        output_path = cover_path
    
    # 读取图片
    image = cv2.imread(cover_path)
    if image is None:
        print(f"⚠️ 无法读取封面: {cover_path}")
        return
    
    h, w = image.shape[:2]
    
    # 添加半透明背景条
    overlay = image.copy()
    cv2.rectangle(overlay, (0, h - 100), (w, h), (0, 0, 0), -1)
    image = cv2.addWeighted(overlay, 0.5, image, 0.5, 0)
    
    # 添加文字
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    thickness = 3
    
    # 计算文字大小以居中
    text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
    text_x = (w - text_size[0]) // 2
    text_y = h - 40
    
    # 绘制文字（白色带黑边）
    cv2.putText(image, title, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 2)
    cv2.putText(image, title, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
    
    success = cv2.imwrite(output_path, image)
    if success:
        print(f"✅ 标题已添加: {output_path}")
    else:
        print(f"⚠️ 标题保存失败: {output_path}")


# 使用示例
if __name__ == "__main__":
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        # 生成封面
        cover = auto_generate_cover(test_video, "cover.jpg")
        
        # 添加标题
        if cover:
            add_title_to_cover("cover.jpg", "精彩解说")
    else:
        print(f"⚠️ 测试视频不存在: {test_video}")
        print("请提供一个视频文件进行测试")

