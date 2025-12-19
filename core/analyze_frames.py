# core/analyze_frames.py - Chinese-CLIP画面分析（🇨🇳 国内版）
"""
SmartVideoClipper - 画面分析模块

功能: 使用Chinese-CLIP分析视频画面，识别场景类型
用途: 找出重要镜头（打斗、浪漫、搞笑等）

依赖: cn-clip, torch, opencv-python, pillow
"""

import torch
from PIL import Image
import cv2
import numpy as np
from typing import List, Dict
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Chinese-CLIP (国内版，无需VPN)
CLIP_SOURCE = "cn_clip"

try:
    import cn_clip.clip as clip
    from cn_clip.clip import load_from_name
    CLIP_SOURCE = "chinese_clip"
except ImportError:
    try:
        # 备选方案
        from cn_clip import clip
        from cn_clip.clip import load_from_name
    except ImportError:
        print("⚠️ Chinese-CLIP未安装，请运行: pip install cn-clip")
        clip = None
        load_from_name = None


class CLIPAnalyzer:
    """使用Chinese-CLIP分析视频画面"""
    
    # 场景类型（中文）
    SCENE_TYPES = [
        "两人对话场景",
        "多人群戏场景",
        "打斗动作场景",
        "追逐场景",
        "浪漫爱情场景",
        "悲伤哭泣场景",
        "搞笑幽默场景",
        "紧张悬疑场景",
        "风景空镜头",
        "特写镜头",
        "普通过渡镜头"
    ]
    
    def __init__(self, model_name: str = "ViT-B-16"):
        """
        初始化CLIP分析器
        
        参数:
            model_name: CLIP模型名称 (ViT-B-16, ViT-L-14, ViT-H-14)
        """
        if clip is None:
            raise ImportError("Chinese-CLIP未安装，请运行: pip install cn-clip")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🖼️ 加载Chinese-CLIP (来源: {CLIP_SOURCE})...")
        print(f"   设备: {self.device}, 模型: {model_name}")
        
        # 加载模型
        self.model, self.preprocess = load_from_name(
            model_name, 
            device=self.device, 
            download_root='./models'
        )
        self.model.eval()
        
        # 预计算场景类型的文本特征
        self._prepare_text_features()
        print("✅ Chinese-CLIP加载完成")
    
    def _prepare_text_features(self):
        """预计算场景类型的文本特征"""
        text_tokens = clip.tokenize(self.SCENE_TYPES).to(self.device)
        with torch.no_grad():
            self.text_features = self.model.encode_text(text_tokens)
            self.text_features /= self.text_features.norm(dim=-1, keepdim=True)
    
    def analyze_frame(self, frame: np.ndarray) -> Dict:
        """
        分析单帧画面
        
        参数:
            frame: OpenCV格式的图像帧 (BGR)
        
        返回:
            {'top_scene': '场景类型', 'confidence': 0.8, 'all_scores': {...}}
        """
        # 转换为PIL图像
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image_input = self.preprocess(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            image_features = self.model.encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
            # 计算相似度
            similarity = (image_features @ self.text_features.T).squeeze()
            probs = similarity.softmax(dim=-1)
        
        # 获取结果
        probs_np = probs.cpu().numpy()
        top_idx = probs_np.argmax()
        
        # 获取前3个最可能的场景
        top_indices = probs_np.argsort()[-3:][::-1]
        
        return {
            'top_scene': self.SCENE_TYPES[top_idx],
            'confidence': float(probs_np[top_idx]),
            'top3': {
                self.SCENE_TYPES[i]: float(probs_np[i])
                for i in top_indices
            }
        }
    
    def analyze_video_scenes(self, video_path: str, scenes: List[Dict]) -> List[Dict]:
        """
        分析每个镜头的中间帧
        
        参数:
            video_path: 视频路径
            scenes: 镜头列表 [{'start': 0, 'end': 5, ...}, ...]
        
        返回:
            分析后的镜头列表，增加了scene_type, confidence, is_important字段
        """
        print(f"🖼️ 开始CLIP画面分析: {len(scenes)}个镜头")
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        analyzed_scenes = []
        for i, scene in enumerate(scenes):
            # 取镜头中间帧
            mid_time = (scene['start'] + scene['end']) / 2
            cap.set(cv2.CAP_PROP_POS_MSEC, mid_time * 1000)
            ret, frame = cap.read()
            
            if ret:
                analysis = self.analyze_frame(frame)
                scene_info = {
                    **scene,
                    'scene_type': analysis['top_scene'],
                    'confidence': analysis['confidence'],
                    'is_important': analysis['confidence'] > 0.3 and 
                                   analysis['top_scene'] not in ['普通过渡镜头', '风景空镜头']
                }
                analyzed_scenes.append(scene_info)
                
                if (i + 1) % 50 == 0:
                    print(f"  已分析 {i+1}/{len(scenes)} 个镜头")
        
        cap.release()
        
        important_count = sum(1 for s in analyzed_scenes if s['is_important'])
        print(f"✅ 分析完成，发现 {important_count} 个重要镜头")
        
        return analyzed_scenes
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'model'):
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# 使用示例
if __name__ == "__main__":
    # 测试CLIP分析
    try:
        analyzer = CLIPAnalyzer()
        
        # 假设已有镜头列表
        scenes = [{'start': 0, 'end': 5}, {'start': 5, 'end': 10}]
        
        test_video = "test_video.mp4"
        if os.path.exists(test_video):
            analyzed = analyzer.analyze_video_scenes(test_video, scenes)
            
            for scene in analyzed[:5]:
                print(f"镜头 {scene['start']:.1f}s: {scene['scene_type']} ({scene['confidence']:.2f})")
        else:
            print(f"⚠️ 测试视频不存在: {test_video}")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")

