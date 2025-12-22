# core/video_content_analyzer.py - 视频内容分析器
"""
SmartVideoClipper v4.0 - 基于视频内容的解说生成

核心理念：看画面写解说，不是写解说找画面

工作流程：
1. 分析视频每个场景的内容（用CLIP分析画面）
2. 结合字幕理解每个场景在讲什么
3. 为每个场景生成对应的解说
4. 解说和画面一一对应

这才是真正的解说博主做法！
"""

import cv2
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional
import os
from pathlib import Path


class VideoContentAnalyzer:
    """
    视频内容分析器
    
    核心功能：分析视频每个场景的内容，生成结构化描述
    """
    
    def __init__(self):
        self.clip_model = None
        self.preprocess = None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._load_models()
    
    def _load_models(self):
        """加载CLIP模型"""
        try:
            import cn_clip.clip as clip
            from cn_clip.clip import load_from_name
            
            print("[CLIP] 加载视觉分析模型...")
            self.clip_model, self.preprocess = load_from_name(
                "ViT-B-16",
                device=self.device,
                download_root='./models'
            )
            self.clip_model.eval()
            self.tokenizer = clip.tokenize
            print(f"[CLIP] 模型加载完成，设备: {self.device}")
        except Exception as e:
            print(f"[WARNING] CLIP加载失败: {e}")
            self.clip_model = None
    
    def analyze_video(
        self,
        video_path: str,
        scenes: List[Dict],
        transcript_segments: List[Dict],
        sample_interval: float = 5.0
    ) -> List[Dict]:
        """
        分析视频内容
        
        参数：
            video_path: 视频路径
            scenes: 场景列表（带时间戳）
            transcript_segments: 字幕片段
            sample_interval: 采样间隔（秒）
        
        返回：
        [
            {
                'scene_id': 1,
                'start_time': 0.0,
                'end_time': 30.0,
                'visual_content': '一个男人在街上走',
                'dialogue': '你好啊',
                'emotion': '平静',
                'scene_type': 'dialogue',  # dialogue/action/transition/emotion
                'importance': 0.8,
                'suggested_narration': '画面中，男主角...',
                'keep_original_audio': False,
            },
            ...
        ]
        """
        print("\n" + "="*60)
        print("🎬 视频内容分析器 v4.0")
        print("   核心：看画面写解说")
        print("="*60)
        
        if not os.path.exists(video_path):
            print(f"[ERROR] 视频不存在: {video_path}")
            return []
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration = total_frames / fps if fps > 0 else 0
        
        print(f"   视频时长: {total_duration:.0f}秒")
        print(f"   场景数量: {len(scenes)}")
        print(f"   字幕数量: {len(transcript_segments)}")
        
        # 分析每个场景
        analyzed_scenes = []
        
        # 场景分类标签（用于CLIP分析）
        scene_labels = [
            "两个人在对话", "一个人在说话", "打斗场面", "追逐场面",
            "安静的场景", "紧张的场面", "悲伤的场景", "快乐的场景",
            "室内场景", "室外场景", "夜晚场景", "白天场景",
            "特写镜头", "远景镜头", "会议场景", "吃饭场景",
            "开车场景", "走路场景", "拥抱场景", "哭泣场景"
        ]
        
        # 情感词汇
        emotion_keywords = {
            'tense': ['快', '小心', '危险', '跑', '追', '杀', '枪'],
            'sad': ['哭', '对不起', '死', '失去', '再见', '离开'],
            'angry': ['滚', '混蛋', '为什么', '凭什么'],
            'happy': ['哈哈', '太好了', '开心', '喜欢'],
            'neutral': []
        }
        
        print("\n[分析] 开始逐场景分析...")
        
        for i, scene in enumerate(scenes[:50]):  # 限制分析前50个场景
            scene_start = scene.get('start', scene.get('start_time', 0))
            scene_end = scene.get('end', scene.get('end_time', scene_start + 5))
            
            # 转换帧数到秒数（如果需要）
            if scene_start > 1000:
                scene_start = scene_start / fps
                scene_end = scene_end / fps
            
            # 分析视觉内容
            visual_content = ""
            scene_type = "unknown"
            
            if self.clip_model:
                mid_time = (scene_start + scene_end) / 2
                cap.set(cv2.CAP_PROP_POS_MSEC, mid_time * 1000)
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    visual_content, scene_type = self._analyze_frame_content(
                        frame, scene_labels
                    )
            
            # 获取该场景的对话
            scene_dialogues = []
            for seg in transcript_segments:
                seg_start = seg.get('start', 0)
                seg_end = seg.get('end', seg_start + 3)
                if seg_start >= scene_start and seg_end <= scene_end + 5:
                    scene_dialogues.append(seg.get('text', ''))
            
            dialogue_text = ' '.join(scene_dialogues)
            
            # 判断情感
            emotion = self._detect_emotion(dialogue_text, emotion_keywords)
            
            # 判断是否应该保留原声
            keep_original = self._should_keep_original(
                dialogue_text, visual_content, scene_type, emotion
            )
            
            # 计算重要性
            importance = self._calculate_importance(
                dialogue_text, visual_content, scene_type, emotion
            )
            
            analyzed_scene = {
                'scene_id': i + 1,
                'start_time': scene_start,
                'end_time': scene_end,
                'duration': scene_end - scene_start,
                'visual_content': visual_content,
                'dialogue': dialogue_text[:200] if dialogue_text else '',
                'emotion': emotion,
                'scene_type': scene_type,
                'importance': importance,
                'keep_original_audio': keep_original,
            }
            
            analyzed_scenes.append(analyzed_scene)
            
            if (i + 1) % 10 == 0:
                print(f"   已分析 {i+1}/{min(len(scenes), 50)} 个场景")
        
        cap.release()
        
        # 按重要性排序，选择关键场景
        analyzed_scenes.sort(key=lambda x: x['importance'], reverse=True)
        
        print(f"\n✅ 分析完成，共 {len(analyzed_scenes)} 个场景")
        print(f"   高重要性场景: {sum(1 for s in analyzed_scenes if s['importance'] > 0.7)}")
        print(f"   保留原声场景: {sum(1 for s in analyzed_scenes if s['keep_original_audio'])}")
        
        return analyzed_scenes
    
    def _analyze_frame_content(
        self,
        frame: np.ndarray,
        labels: List[str]
    ) -> Tuple[str, str]:
        """用CLIP分析帧内容"""
        try:
            from PIL import Image
            import cn_clip.clip as clip
            
            # 转换图像
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            # 预处理
            image_input = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            text_inputs = self.tokenizer(labels).to(self.device)
            
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_input)
                text_features = self.clip_model.encode_text(text_inputs)
                
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                similarity = (image_features @ text_features.T).squeeze()
                
                # 获取top匹配
                top_idx = similarity.argmax().item()
                top_label = labels[top_idx]
                
                # 判断场景类型
                if any(kw in top_label for kw in ['对话', '说话']):
                    scene_type = 'dialogue'
                elif any(kw in top_label for kw in ['打斗', '追逐', '紧张']):
                    scene_type = 'action'
                elif any(kw in top_label for kw in ['悲伤', '哭泣']):
                    scene_type = 'emotion'
                else:
                    scene_type = 'transition'
                
                return top_label, scene_type
                
        except Exception as e:
            return "未知场景", "unknown"
    
    def _detect_emotion(self, dialogue: str, emotion_keywords: Dict) -> str:
        """检测情感"""
        for emotion, keywords in emotion_keywords.items():
            if any(kw in dialogue for kw in keywords):
                return emotion
        return 'neutral'
    
    def _should_keep_original(
        self,
        dialogue: str,
        visual: str,
        scene_type: str,
        emotion: str
    ) -> bool:
        """判断是否应该保留原声"""
        # 重要对话场景保留原声
        if scene_type == 'dialogue' and len(dialogue) > 30:
            return True
        
        # 高情感强度场景保留原声
        if emotion in ['tense', 'sad', 'angry']:
            return True
        
        # 动作场景保留原声
        if scene_type == 'action':
            return True
        
        return False
    
    def _calculate_importance(
        self,
        dialogue: str,
        visual: str,
        scene_type: str,
        emotion: str
    ) -> float:
        """计算场景重要性"""
        score = 0.5  # 基础分
        
        # 有对话加分
        if dialogue:
            score += 0.1 + min(0.2, len(dialogue) / 200)
        
        # 情感场景加分
        if emotion in ['tense', 'sad', 'angry']:
            score += 0.2
        
        # 动作场景加分
        if scene_type == 'action':
            score += 0.15
        
        # 对话场景加分
        if scene_type == 'dialogue':
            score += 0.1
        
        return min(1.0, score)
    
    def generate_scene_narrations(
        self,
        analyzed_scenes: List[Dict],
        target_duration: int,
        style: str = "幽默"
    ) -> List[Dict]:
        """
        为每个场景生成对应的解说
        
        这是关键！解说是针对具体画面的，不是泛泛而谈
        """
        print("\n" + "="*60)
        print("📝 场景解说生成器")
        print(f"   目标时长: {target_duration}秒")
        print("="*60)
        
        # 按时间排序
        scenes = sorted(analyzed_scenes, key=lambda x: x['start_time'])
        
        # 计算需要多少场景
        avg_scene_duration = 15  # 平均每个场景15秒
        needed_scenes = target_duration // avg_scene_duration
        
        # 选择最重要的场景
        important_scenes = sorted(scenes, key=lambda x: x['importance'], reverse=True)
        selected_scenes = important_scenes[:needed_scenes]
        selected_scenes.sort(key=lambda x: x['start_time'])  # 按时间排序
        
        print(f"   选择了 {len(selected_scenes)} 个关键场景")
        
        # 为每个场景生成解说
        result_scenes = []
        
        for scene in selected_scenes:
            if scene['keep_original_audio']:
                # 保留原声的场景，不需要解说
                scene['narration'] = ''
                scene['narration_type'] = 'original'
            else:
                # 需要解说的场景
                narration = self._generate_single_narration(
                    scene, style
                )
                scene['narration'] = narration
                scene['narration_type'] = 'voiceover'
            
            result_scenes.append(scene)
        
        print(f"   解说场景: {sum(1 for s in result_scenes if s['narration_type'] == 'voiceover')}")
        print(f"   原声场景: {sum(1 for s in result_scenes if s['narration_type'] == 'original')}")
        
        return result_scenes
    
    def _generate_single_narration(self, scene: Dict, style: str) -> str:
        """为单个场景生成解说"""
        visual = scene.get('visual_content', '')
        dialogue = scene.get('dialogue', '')
        emotion = scene.get('emotion', 'neutral')
        scene_type = scene.get('scene_type', 'unknown')
        
        # 基于场景内容生成解说
        # 这里可以用AI，但先用模板确保基本可用
        
        narration_templates = {
            'dialogue': [
                f"画面中，{visual}。",
                f"此时，{visual}。",
                f"镜头里，{visual}。",
            ],
            'action': [
                f"紧张的一幕出现了，{visual}。",
                f"画面急转，{visual}。",
                f"此刻，{visual}。",
            ],
            'emotion': [
                f"情绪达到顶点，{visual}。",
                f"令人动容的一幕，{visual}。",
                f"在这一刻，{visual}。",
            ],
            'transition': [
                f"画面一转，{visual}。",
                f"镜头切换到，{visual}。",
                f"接下来，{visual}。",
            ],
        }
        
        templates = narration_templates.get(scene_type, narration_templates['transition'])
        
        import random
        base_narration = random.choice(templates)
        
        # 如果有对话，可以提及
        if dialogue and len(dialogue) > 10:
            base_narration += f" {dialogue[:50]}..."
        
        return base_narration


def create_scene_based_timeline(
    analyzed_scenes: List[Dict],
    target_duration: int
) -> List[Dict]:
    """
    创建基于场景的剪辑时间线
    
    关键：解说或原声二选一，不混合！
    """
    timeline = []
    output_cursor = 0.0
    
    for scene in analyzed_scenes:
        if scene['narration_type'] == 'original':
            # 原声场景：使用原视频音频
            audio_mode = 'original'
            narration_text = ''
        else:
            # 解说场景：使用TTS解说
            audio_mode = 'voiceover'
            narration_text = scene.get('narration', '')
        
        duration = scene['end_time'] - scene['start_time']
        
        timeline.append({
            'scene_id': scene['scene_id'],
            'source_start': scene['start_time'],
            'source_end': scene['end_time'],
            'output_start': output_cursor,
            'output_end': output_cursor + duration,
            'audio_mode': audio_mode,  # 'original' 或 'voiceover'
            'narration_text': narration_text,
            'visual_content': scene.get('visual_content', ''),
            'importance': scene.get('importance', 0.5),
        })
        
        output_cursor += duration
    
    return timeline


# 测试
if __name__ == "__main__":
    analyzer = VideoContentAnalyzer()
    
    # 模拟测试
    test_scenes = [
        {'start': 0, 'end': 30},
        {'start': 100, 'end': 130},
        {'start': 500, 'end': 530},
    ]
    
    test_segments = [
        {'start': 10, 'end': 15, 'text': '你好啊'},
        {'start': 110, 'end': 120, 'text': '我要杀了你！'},
    ]
    
    # 如果有视频文件可以测试
    # result = analyzer.analyze_video("test.mp4", test_scenes, test_segments)

