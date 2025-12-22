# core/semantic_matcher.py - 语义匹配素材选择器
"""
SmartVideoClipper v3.0 - 语义匹配素材选择器

核心功能：根据解说剧本中的场景描述，精确匹配原视频画面

技术方案：
1. Chinese-CLIP: 计算文本-图像相似度
2. 对话匹配：根据字幕内容匹配场景
3. 时间约束：在指定时间范围内搜索

这是实现"解说-画面同步"的关键！
"""

import cv2
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional
import os


class SemanticMatcher:
    """
    语义匹配器
    
    输入：解说剧本 + 视频帧 + 字幕
    输出：每段解说对应的精确视频片段
    """
    
    def __init__(self):
        self.clip_model = None
        self.clip_preprocess = None
        self.tokenizer = None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._load_clip()
    
    def _load_clip(self):
        """加载Chinese-CLIP模型"""
        try:
            import cn_clip.clip as clip
            from cn_clip.clip import load_from_name
            
            print("[CLIP] 加载 Chinese-CLIP 模型...")
            self.clip_model, self.clip_preprocess = load_from_name(
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
    
    def match_segments(
        self,
        video_path: str,
        script_segments: List[Dict],
        transcript_segments: List[Dict],
        scenes: List[Dict]
    ) -> List[Dict]:
        """
        为每段解说匹配最佳视频素材
        
        参数：
            video_path: 视频文件路径
            script_segments: 解说剧本段落
            transcript_segments: 字幕片段（带时间戳）
            scenes: 场景列表（带时间戳）
        
        返回：
            更新后的script_segments，每段包含matched_clips
        """
        print("\n" + "="*60)
        print("🔍 语义匹配素材选择器 v3.0")
        print("="*60)
        
        if not os.path.exists(video_path):
            print(f"[ERROR] 视频不存在: {video_path}")
            return script_segments
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration = total_frames / fps if fps > 0 else 0
        
        print(f"   视频时长: {total_duration:.0f}秒")
        print(f"   解说段落: {len(script_segments)}段")
        
        # 为每段匹配素材
        for i, seg in enumerate(script_segments):
            print(f"\n[{i+1}/{len(script_segments)}] 匹配: {seg.get('phase', '未知段落')}")
            
            # 获取搜索时间范围
            time_range = seg.get('source_time_range', [0, total_duration])
            start_time, end_time = time_range
            
            # 获取场景描述
            scene_desc = seg.get('scene_description', '')
            narration = seg.get('narration_text', '')
            
            # 多策略匹配
            matched_clips = []
            
            # 策略1：基于CLIP的视觉匹配
            if self.clip_model and scene_desc:
                clip_matches = self._match_by_clip(
                    cap, fps, scene_desc, start_time, end_time
                )
                matched_clips.extend(clip_matches)
                print(f"   [CLIP] 找到 {len(clip_matches)} 个匹配")
            
            # 策略2：基于对话的匹配
            dialogue_matches = self._match_by_dialogue(
                transcript_segments, narration, start_time, end_time
            )
            matched_clips.extend(dialogue_matches)
            print(f"   [对话] 找到 {len(dialogue_matches)} 个匹配")
            
            # 策略3：基于场景切换的匹配
            scene_matches = self._match_by_scenes(
                scenes, start_time, end_time, seg.get('duration', 30)
            )
            matched_clips.extend(scene_matches)
            print(f"   [场景] 找到 {len(scene_matches)} 个匹配")
            
            # 合并和去重
            final_clips = self._merge_clips(matched_clips, seg.get('duration', 30))
            seg['matched_clips'] = final_clips
            
            print(f"   ✓ 最终选取 {len(final_clips)} 个片段")
        
        cap.release()
        
        print("\n" + "="*60)
        print("✅ 素材匹配完成！")
        print("="*60)
        
        return script_segments
    
    def _match_by_clip(
        self,
        cap: cv2.VideoCapture,
        fps: float,
        scene_description: str,
        start_time: float,
        end_time: float,
        sample_interval: float = 3.0
    ) -> List[Dict]:
        """使用CLIP进行视觉-文本匹配"""
        
        if not self.clip_model:
            return []
        
        matches = []
        
        try:
            import cn_clip.clip as clip
            from PIL import Image
            
            # 编码文本
            text = self.tokenizer([scene_description]).to(self.device)
            with torch.no_grad():
                text_features = self.clip_model.encode_text(text)
                text_features /= text_features.norm(dim=-1, keepdim=True)
            
            # 采样帧并计算相似度
            candidates = []
            
            for t in np.arange(start_time, end_time, sample_interval):
                frame_num = int(t * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    continue
                
                # 转换为PIL图像
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                
                # 预处理并编码
                image_input = self.clip_preprocess(pil_image).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    image_features = self.clip_model.encode_image(image_input)
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                
                # 计算相似度
                similarity = (text_features @ image_features.T).item()
                
                candidates.append({
                    'time': t,
                    'similarity': similarity,
                    'method': 'clip'
                })
            
            # 选择top匹配
            candidates.sort(key=lambda x: x['similarity'], reverse=True)
            
            for cand in candidates[:3]:  # 最多3个
                if cand['similarity'] > 0.2:  # 相似度阈值
                    matches.append({
                        'start': cand['time'],
                        'end': cand['time'] + 5,
                        'score': cand['similarity'],
                        'method': 'clip'
                    })
            
        except Exception as e:
            print(f"   [WARNING] CLIP匹配失败: {e}")
        
        return matches
    
    def _match_by_dialogue(
        self,
        transcript_segments: List[Dict],
        narration_text: str,
        start_time: float,
        end_time: float
    ) -> List[Dict]:
        """基于对话内容匹配"""
        
        matches = []
        
        # 提取解说中的关键词
        keywords = self._extract_keywords(narration_text)
        
        for seg in transcript_segments:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', seg_start + 3)
            seg_text = seg.get('text', '')
            
            # 检查时间范围
            if seg_start < start_time or seg_end > end_time:
                continue
            
            # 计算匹配度
            match_score = 0
            for kw in keywords:
                if kw in seg_text:
                    match_score += 1
            
            if match_score > 0:
                matches.append({
                    'start': seg_start,
                    'end': seg_end,
                    'score': match_score / max(len(keywords), 1),
                    'method': 'dialogue',
                    'matched_text': seg_text
                })
        
        # 按分数排序
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return matches[:5]  # 最多5个
    
    def _match_by_scenes(
        self,
        scenes: List[Dict],
        start_time: float,
        end_time: float,
        target_duration: float
    ) -> List[Dict]:
        """基于场景切换匹配"""
        
        matches = []
        
        # 找到时间范围内的场景
        for scene in scenes:
            scene_start = scene.get('start', scene.get('start_time', 0))
            scene_end = scene.get('end', scene.get('end_time', scene_start + 5))
            
            # 时间转换（如果是帧数）
            if scene_start > 1000:  # 可能是帧数
                scene_start = scene_start / 25  # 假设25fps
                scene_end = scene_end / 25
            
            if scene_start >= start_time and scene_end <= end_time:
                duration = scene_end - scene_start
                
                matches.append({
                    'start': scene_start,
                    'end': scene_end,
                    'score': min(duration / target_duration, 1.0),
                    'method': 'scene',
                    'duration': duration
                })
        
        # 按时间排序
        matches.sort(key=lambda x: x['start'])
        
        return matches
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
        
        # 情感词
        emotion_words = ['愤怒', '悲伤', '惊讶', '恐惧', '紧张', '温情', '冲突',
                        '哭', '笑', '杀', '死', '爱', '恨', '跑', '追']
        
        # 动作词
        action_words = ['打', '跑', '跳', '开枪', '开车', '拥抱', '亲吻', 
                       '对话', '争吵', '逃跑', '追逐', '爆炸']
        
        # 场景词
        scene_words = ['街道', '房间', '警察局', '医院', '学校', '餐厅',
                      '夜晚', '白天', '雨', '雪']
        
        keywords = []
        
        for word in emotion_words + action_words + scene_words:
            if word in text:
                keywords.append(word)
        
        # 提取人名（中文名通常2-3个字）
        name_pattern = r'[\u4e00-\u9fff]{2,3}(?=说|道|问|答|想|看|走|跑)'
        names = re.findall(name_pattern, text)
        keywords.extend(names[:3])
        
        return keywords
    
    def _merge_clips(
        self,
        clips: List[Dict],
        target_duration: float
    ) -> List[Dict]:
        """合并和筛选片段"""
        
        if not clips:
            return []
        
        # 按开始时间排序
        clips.sort(key=lambda x: x['start'])
        
        # 合并重叠片段
        merged = []
        current = clips[0].copy()
        
        for clip in clips[1:]:
            if clip['start'] <= current['end'] + 1:
                # 合并
                current['end'] = max(current['end'], clip['end'])
                current['score'] = max(current['score'], clip['score'])
            else:
                merged.append(current)
                current = clip.copy()
        merged.append(current)
        
        # 按分数排序，选择最佳片段
        merged.sort(key=lambda x: x['score'], reverse=True)
        
        # 控制总时长
        selected = []
        total_duration = 0
        
        for clip in merged:
            clip_duration = clip['end'] - clip['start']
            if total_duration + clip_duration <= target_duration * 1.5:
                selected.append(clip)
                total_duration += clip_duration
        
        # 按时间顺序返回
        selected.sort(key=lambda x: x['start'])
        
        return selected


# 智能剪辑器
class SmartClipper:
    """
    智能剪辑器
    
    根据匹配结果执行精确剪辑
    """
    
    def __init__(self):
        pass
    
    def create_timeline(
        self,
        script_segments: List[Dict],
        video_duration: float
    ) -> List[Dict]:
        """
        创建剪辑时间线
        
        返回：
        [
            {
                'clip_id': 1,
                'source_start': 100.0,
                'source_end': 120.0,
                'narration_start': 0.0,
                'narration_end': 20.0,
                'keep_original': False,
            },
            ...
        ]
        """
        timeline = []
        narration_cursor = 0.0
        clip_id = 0
        
        for seg in script_segments:
            matched_clips = seg.get('matched_clips', [])
            narration_duration = seg.get('duration', 30)
            keep_original = seg.get('keep_original_audio', False)
            
            if not matched_clips:
                # 使用建议的时间范围
                time_range = seg.get('source_time_range', [0, 30])
                matched_clips = [{
                    'start': time_range[0],
                    'end': min(time_range[0] + narration_duration, time_range[1])
                }]
            
            # 将素材分配到时间线
            for clip in matched_clips:
                clip_id += 1
                clip_duration = clip['end'] - clip['start']
                
                timeline.append({
                    'clip_id': clip_id,
                    'segment_id': seg.get('segment_id'),
                    'phase': seg.get('phase', ''),
                    'source_start': clip['start'],
                    'source_end': clip['end'],
                    'narration_start': narration_cursor,
                    'narration_end': narration_cursor + clip_duration,
                    'keep_original': keep_original,
                    'narration_text': seg.get('narration_text', '')[:50] + '...'
                })
                
                narration_cursor += clip_duration
        
        return timeline
    
    def print_timeline(self, timeline: List[Dict]):
        """打印时间线"""
        print("\n" + "="*70)
        print("📋 剪辑时间线")
        print("="*70)
        print(f"{'#':<4} {'阶段':<12} {'源视频':<20} {'解说时间':<20} {'原声':<6}")
        print("-"*70)
        
        for item in timeline:
            source = f"{item['source_start']:.1f}s - {item['source_end']:.1f}s"
            narr = f"{item['narration_start']:.1f}s - {item['narration_end']:.1f}s"
            orig = "✓" if item['keep_original'] else ""
            
            print(f"{item['clip_id']:<4} {item['phase']:<12} {source:<20} {narr:<20} {orig:<6}")
        
        print("="*70)


# 测试
if __name__ == "__main__":
    matcher = SemanticMatcher()
    clipper = SmartClipper()
    
    # 模拟数据
    test_script = [
        {
            'segment_id': 1,
            'phase': '开场白',
            'scene_description': '一个男人站在街头',
            'narration_text': '今天要给大家介绍的是一个关于成长的故事',
            'source_time_range': [0, 60],
            'duration': 20,
        },
        {
            'segment_id': 2,
            'phase': '高潮',
            'scene_description': '激烈的冲突场面',
            'narration_text': '此刻，命运的齿轮开始转动',
            'source_time_range': [1000, 1200],
            'duration': 30,
            'keep_original_audio': True,
        },
    ]
    
    test_script[0]['matched_clips'] = [
        {'start': 10, 'end': 25, 'score': 0.8},
        {'start': 40, 'end': 55, 'score': 0.6},
    ]
    test_script[1]['matched_clips'] = [
        {'start': 1050, 'end': 1080, 'score': 0.9},
    ]
    
    timeline = clipper.create_timeline(test_script, 2400)
    clipper.print_timeline(timeline)

