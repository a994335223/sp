# core/duration_controller.py - 智能时长控制器
"""
SmartVideoClipper - 智能时长控制

核心功能：
1. 根据内容自动决定输出时长
2. 解说文本长度适配场景时长
3. 确保输出在目标范围内

设计原则：
- 不硬性裁剪，而是智能选择场景
- 解说文本根据场景时长调整
- 保证剧情连贯性
"""

from typing import List, Dict, Tuple
import math


class DurationController:
    """
    智能时长控制器
    
    职责：
    1. 选择场景以达到目标时长
    2. 调整解说文本长度
    3. 确保原声/解说比例合理
    """
    
    # 解说语速：约每秒4个汉字
    SPEECH_RATE = 4.0
    
    def __init__(
        self,
        min_duration: int = 180,    # 最短3分钟
        max_duration: int = 900,    # 最长15分钟
        original_ratio: float = 0.3  # 至少30%原声
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.original_ratio = original_ratio
    
    def select_scenes(
        self,
        scenes: List[Dict],
        target_duration: int = None
    ) -> Tuple[List[Dict], int]:
        """
        智能选择场景以达到目标时长
        
        参数：
            scenes: 所有场景列表，需要 start_time, end_time, importance, audio_mode
            target_duration: 目标时长（可选，默认根据内容决定）
        
        返回：
            (选中的场景列表, 实际时长)
        """
        if not scenes:
            return [], 0
        
        # 计算总可用时长
        total_available = sum(s['end_time'] - s['start_time'] for s in scenes)
        
        # 如果没有指定目标时长，根据内容决定
        if target_duration is None:
            # 高重要性场景时长
            high_importance_duration = sum(
                s['end_time'] - s['start_time']
                for s in scenes
                if s.get('importance', 0) >= 0.6
            )
            
            # 目标 = 高重要性 * 1.5（加上过渡），限制在范围内
            target_duration = int(high_importance_duration * 1.5)
            target_duration = max(self.min_duration, min(self.max_duration, target_duration))
        
        print(f"\n[DURATION] 智能时长控制")
        print(f"   总可用: {total_available:.0f}秒")
        print(f"   目标: {target_duration}秒 ({target_duration//60}分{target_duration%60}秒)")
        
        # 按重要性排序
        sorted_scenes = sorted(scenes, key=lambda x: x.get('importance', 0), reverse=True)
        
        selected = []
        current_duration = 0
        
        # 第一轮：选择高重要性场景（必须保留）
        for scene in sorted_scenes:
            if scene.get('importance', 0) >= 0.7:
                duration = scene['end_time'] - scene['start_time']
                if current_duration + duration <= self.max_duration:
                    selected.append(scene)
                    current_duration += duration
        
        # 第二轮：填充中等重要性场景
        for scene in sorted_scenes:
            if scene in selected:
                continue
            if scene.get('importance', 0) >= 0.4:
                duration = scene['end_time'] - scene['start_time']
                if current_duration + duration <= target_duration:
                    selected.append(scene)
                    current_duration += duration
        
        # 第三轮：如果还不够最短时长，添加更多场景
        if current_duration < self.min_duration:
            for scene in sorted_scenes:
                if scene in selected:
                    continue
                duration = scene['end_time'] - scene['start_time']
                if current_duration + duration <= self.max_duration:
                    selected.append(scene)
                    current_duration += duration
                if current_duration >= self.min_duration:
                    break
        
        # 按时间排序（保证剧情顺序）
        selected.sort(key=lambda x: x['start_time'])
        
        # 检查原声比例
        selected = self._ensure_original_ratio(selected)
        
        final_duration = sum(s['end_time'] - s['start_time'] for s in selected)
        
        print(f"   选中: {len(selected)}个场景")
        print(f"   实际: {final_duration:.0f}秒 ({final_duration//60:.0f}分{final_duration%60:.0f}秒)")
        
        return selected, int(final_duration)
    
    def _ensure_original_ratio(self, scenes: List[Dict]) -> List[Dict]:
        """确保原声比例"""
        original_count = sum(1 for s in scenes if s.get('audio_mode') == 'original')
        total = len(scenes)
        
        if total == 0:
            return scenes
        
        current_ratio = original_count / total
        
        if current_ratio < self.original_ratio:
            # 原声不够，将部分解说改为原声
            need_convert = int(total * self.original_ratio) - original_count
            
            # 按重要性排序，将最重要的解说场景改为原声
            voiceover_scenes = [s for s in scenes if s.get('audio_mode') == 'voiceover']
            voiceover_scenes.sort(key=lambda x: x.get('importance', 0), reverse=True)
            
            for i, scene in enumerate(voiceover_scenes):
                if i >= need_convert:
                    break
                scene['audio_mode'] = 'original'
                scene['reason'] = scene.get('reason', '') + ' (增加原声比例)'
        
        return scenes
    
    def adjust_narration_length(
        self,
        narration: str,
        target_duration: float,
        style: str = "幽默"
    ) -> str:
        """
        调整解说文本长度以匹配场景时长
        
        参数：
            narration: 原始解说文本
            target_duration: 目标时长（秒）
            style: 解说风格
        
        返回：
            调整后的解说文本
        """
        if not narration:
            return ""
        
        # 当前预估时长
        current_chars = len(narration)
        current_duration = current_chars / self.SPEECH_RATE
        
        # 目标字数
        target_chars = int(target_duration * self.SPEECH_RATE)
        
        # 调整
        if current_chars > target_chars * 1.3:
            # 太长，需要缩短
            # 简单截取（实际应该用AI缩写）
            adjusted = narration[:target_chars]
            # 确保不在中间断句
            for punct in ['。', '，', '！', '？', '；']:
                last_idx = adjusted.rfind(punct)
                if last_idx > target_chars * 0.7:
                    adjusted = adjusted[:last_idx + 1]
                    break
            return adjusted
        
        elif current_chars < target_chars * 0.5:
            # 太短，保持原样（视频会有静音）
            return narration
        
        else:
            # 长度合适
            return narration
    
    def create_optimized_timeline(
        self,
        scenes: List[Dict],
        target_duration: int = None
    ) -> List[Dict]:
        """
        创建优化后的时间线
        
        这是主入口函数
        """
        # 1. 选择场景
        selected_scenes, actual_duration = self.select_scenes(scenes, target_duration)
        
        # 2. 调整解说长度
        for scene in selected_scenes:
            if scene.get('audio_mode') == 'voiceover' and scene.get('narration'):
                scene_duration = scene['end_time'] - scene['start_time']
                scene['narration'] = self.adjust_narration_length(
                    scene['narration'],
                    scene_duration
                )
        
        # 3. 构建时间线
        timeline = []
        output_time = 0
        
        for scene in selected_scenes:
            duration = scene['end_time'] - scene['start_time']
            
            timeline.append({
                'scene_id': scene.get('scene_id', len(timeline) + 1),
                'source_start': scene['start_time'],
                'source_end': scene['end_time'],
                'output_start': output_time,
                'output_end': output_time + duration,
                'duration': duration,
                'audio_mode': scene.get('audio_mode', 'original'),
                'narration': scene.get('narration', ''),
                'dialogue': scene.get('dialogue', ''),
                'importance': scene.get('importance', 0.5),
                'emotion': scene.get('emotion', 'neutral'),
                'reason': scene.get('reason', ''),
            })
            
            output_time += duration
        
        # 打印统计
        orig_count = sum(1 for t in timeline if t['audio_mode'] == 'original')
        voice_count = sum(1 for t in timeline if t['audio_mode'] == 'voiceover')
        
        print(f"\n[TIMELINE] 时间线生成完成")
        print(f"   🔊 原声: {orig_count} ({orig_count*100//(orig_count+voice_count+1)}%)")
        print(f"   🎙️ 解说: {voice_count} ({voice_count*100//(orig_count+voice_count+1)}%)")
        print(f"   ⏱️ 总时长: {output_time:.0f}秒")
        
        return timeline


def estimate_narration_duration(text: str, speech_rate: float = 4.0) -> float:
    """估算解说时长"""
    if not text:
        return 0
    return len(text) / speech_rate


# 测试
if __name__ == "__main__":
    controller = DurationController(
        min_duration=180,
        max_duration=600
    )
    
    # 模拟场景
    test_scenes = [
        {'start_time': 0, 'end_time': 30, 'importance': 0.9, 'audio_mode': 'original'},
        {'start_time': 30, 'end_time': 60, 'importance': 0.5, 'audio_mode': 'voiceover', 'narration': '这是一段解说'},
        {'start_time': 60, 'end_time': 90, 'importance': 0.3, 'audio_mode': 'voiceover'},
        {'start_time': 90, 'end_time': 150, 'importance': 0.8, 'audio_mode': 'original'},
        {'start_time': 150, 'end_time': 200, 'importance': 0.6, 'audio_mode': 'voiceover'},
    ]
    
    timeline = controller.create_optimized_timeline(test_scenes, target_duration=240)
    
    print("\n生成的时间线:")
    for t in timeline:
        mode = "🔊" if t['audio_mode'] == 'original' else "🎙️"
        print(f"  {t['source_start']:.0f}s-{t['source_end']:.0f}s {mode} 重要性:{t['importance']:.1f}")

