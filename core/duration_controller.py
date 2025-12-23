# core/duration_controller.py - 智能时长控制器 v5.5
"""
SmartVideoClipper - 智能时长控制 v5.5

v5.5核心改进：
1. 智能时长计算：根据剧情复杂度、对话密度自动计算
2. 完整故事覆盖：确保能讲完整个故事
3. 不再固定时长：基于内容动态调整

设计原则：
- 让观众"X分钟看完整部剧"
- 覆盖所有关键剧情点
- 时长根据内容复杂度自动调整
"""

from typing import List, Dict, Tuple
import math


class DurationController:
    """
    智能时长控制器 v5.5
    
    职责：
    1. 智能计算目标时长（根据内容复杂度）
    2. 选择场景以覆盖完整故事
    3. 确保剧情连贯性
    
    v5.5改进：
    - calculate_story_duration: 基于内容计算时长
    - select_scenes_for_complete_story: 确保故事完整
    """
    
    # 解说语速：约每秒4个汉字
    SPEECH_RATE = 4.0
    
    # 时长计算参数
    MIN_DURATION_RATIO = 0.10   # 最少是原片的10%
    MAX_DURATION_RATIO = 0.25   # 最多是原片的25%
    BASE_RATIO = 0.15           # 基础比例15%
    
    def __init__(
        self,
        min_duration: int = 180,    # 最短3分钟
        max_duration: int = 900,    # 最长15分钟
        original_ratio: float = 0.3  # 至少30%原声
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.original_ratio = original_ratio
    
    def calculate_story_duration(
        self,
        scenes: List[Dict],
        media_type: str = "tv",
        episode_plot: str = ""
    ) -> Tuple[int, int, int]:
        """
        智能计算目标时长 v5.5
        
        核心逻辑：
        1. 基于原片时长计算基础比例
        2. 根据剧情复杂度调整
        3. 根据对话密度调整
        4. 根据重要场景数量调整
        
        返回：(推荐时长, 最小时长, 最大时长)
        """
        if not scenes:
            return (180, 180, 300)
        
        # 原片总时长
        total_duration = sum(s.get('end_time', 0) - s.get('start_time', 0) for s in scenes)
        
        print(f"\n[DURATION] 智能时长计算 v5.5")
        print(f"   原片时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        
        # ============ 因素1：剧情复杂度 ============
        # 通过剧情概要长度估算
        plot_complexity = 1.0
        if episode_plot:
            plot_length = len(episode_plot)
            if plot_length > 500:
                plot_complexity = 1.2  # 复杂剧情需要更多时间讲述
            elif plot_length > 300:
                plot_complexity = 1.1
            elif plot_length < 100:
                plot_complexity = 0.9  # 简单剧情可以更快讲完
        print(f"   剧情复杂度系数: {plot_complexity}")
        
        # ============ 因素2：对话密度 ============
        # 统计有对话的场景
        dialogue_count = sum(1 for s in scenes if s.get('dialogue', '').strip())
        dialogue_density = dialogue_count / len(scenes) if scenes else 0
        
        dialogue_factor = 1.0
        if dialogue_density > 0.7:
            dialogue_factor = 1.15  # 对话多需要更多时间
        elif dialogue_density < 0.3:
            dialogue_factor = 0.9  # 对话少可以加快
        print(f"   对话密度: {dialogue_density*100:.0f}%, 系数: {dialogue_factor}")
        
        # ============ 因素3：重要场景占比 ============
        # 高重要性场景必须保留
        high_importance = sum(1 for s in scenes if s.get('importance', 0) >= 0.7)
        mid_importance = sum(1 for s in scenes if 0.4 <= s.get('importance', 0) < 0.7)
        
        importance_factor = 1.0
        important_ratio = (high_importance + mid_importance * 0.5) / len(scenes) if scenes else 0
        if important_ratio > 0.5:
            importance_factor = 1.15  # 重要场景多需要更多时间
        elif important_ratio < 0.2:
            importance_factor = 0.9
        print(f"   重要场景占比: {important_ratio*100:.0f}%, 系数: {importance_factor}")
        
        # ============ 计算最终时长 ============
        # 基础时长 = 原片 * 基础比例
        base_duration = total_duration * self.BASE_RATIO
        
        # 调整后时长
        adjusted_duration = base_duration * plot_complexity * dialogue_factor * importance_factor
        
        # 根据媒体类型微调
        if media_type == "tv":
            # 电视剧单集：5-12分钟
            adjusted_duration = max(300, min(720, adjusted_duration))
        else:
            # 电影：8-20分钟
            adjusted_duration = max(480, min(1200, adjusted_duration))
        
        # 计算最小/最大范围
        min_duration = int(adjusted_duration * 0.8)
        max_duration = int(adjusted_duration * 1.3)
        recommended = int(adjusted_duration)
        
        # 绝对限制
        min_duration = max(180, min_duration)  # 至少3分钟
        max_duration = min(1200, max_duration)  # 最多20分钟
        
        print(f"   推荐时长: {recommended}秒 ({recommended//60}分{recommended%60}秒)")
        print(f"   范围: {min_duration}秒 - {max_duration}秒")
        
        return (recommended, min_duration, max_duration)
    
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
    
    def select_scenes_for_complete_story(
        self,
        scenes: List[Dict],
        target_duration: int,
        min_duration: int,
        max_duration: int
    ) -> Tuple[List[Dict], int]:
        """
        为完整故事选择场景 v5.5
        
        核心原则：
        1. 关键剧情点必须保留（开头、高潮、结尾）
        2. 对话密集场景优先（承载主要信息）
        3. 情感强烈场景优先（观众记忆点）
        4. 过渡场景适当保留（连贯性）
        """
        if not scenes:
            return [], 0
        
        total_scenes = len(scenes)
        total_available = sum(s.get('end_time', 0) - s.get('start_time', 0) for s in scenes)
        
        print(f"\n[SELECT] 智能场景选择 v5.5 (完整故事模式)")
        print(f"   场景总数: {total_scenes}")
        print(f"   可用时长: {total_available:.0f}秒")
        print(f"   目标范围: {min_duration}-{max_duration}秒")
        
        # ===== 第一步：标记关键位置场景 =====
        # 开头10%、中间高潮、结尾10%
        start_idx = int(total_scenes * 0.1)
        end_idx = int(total_scenes * 0.9)
        
        key_scenes = set()
        
        # 开头场景（建立背景）
        for i in range(min(start_idx, 5)):
            key_scenes.add(i)
        
        # 结尾场景（收尾）
        for i in range(max(end_idx, total_scenes - 5), total_scenes):
            key_scenes.add(i)
        
        # ===== 第二步：按重要性+对话+情感打分 =====
        scored_scenes = []
        for i, scene in enumerate(scenes):
            score = scene.get('importance', 0.5)
            
            # 对话加分
            dialogue = scene.get('dialogue', '')
            if dialogue and len(dialogue) > 30:
                score += 0.2
            elif dialogue and len(dialogue) > 10:
                score += 0.1
            
            # 情感加分
            emotion = scene.get('emotion', 'neutral')
            if emotion in ['angry', 'sad', 'excited']:
                score += 0.15
            
            # 关键位置加分
            if i in key_scenes:
                score += 0.25
            
            scored_scenes.append({
                'index': i,
                'scene': scene,
                'score': min(score, 1.0),  # 最高1.0
                'duration': scene.get('end_time', 0) - scene.get('start_time', 0)
            })
        
        # 按分数排序
        scored_scenes.sort(key=lambda x: x['score'], reverse=True)
        
        # ===== 第三步：选择场景直到达到目标时长 =====
        selected_indices = set()
        current_duration = 0
        
        # 先添加关键位置场景
        for item in scored_scenes:
            if item['index'] in key_scenes:
                if current_duration + item['duration'] <= max_duration:
                    selected_indices.add(item['index'])
                    current_duration += item['duration']
        
        # 再添加高分场景直到达到目标
        for item in scored_scenes:
            if item['index'] in selected_indices:
                continue
            
            if current_duration + item['duration'] <= target_duration:
                selected_indices.add(item['index'])
                current_duration += item['duration']
            
            if current_duration >= target_duration:
                break
        
        # 如果还不够最小时长，继续添加
        if current_duration < min_duration:
            for item in scored_scenes:
                if item['index'] in selected_indices:
                    continue
                
                if current_duration + item['duration'] <= max_duration:
                    selected_indices.add(item['index'])
                    current_duration += item['duration']
                
                if current_duration >= min_duration:
                    break
        
        # 按原始顺序输出
        selected = [scenes[i] for i in sorted(selected_indices)]
        
        print(f"   选中: {len(selected)}/{total_scenes}个场景 ({len(selected)*100//total_scenes}%)")
        print(f"   实际时长: {current_duration:.0f}秒 ({current_duration/60:.1f}分钟)")
        
        return selected, int(current_duration)
    
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
    
    def _merge_short_scenes(self, scenes: List[Dict], min_duration: float = 3.0) -> List[Dict]:
        """
        合并相邻的短场景（减少TTS碎片化）
        
        规则：
        1. 相邻场景audio_mode相同
        2. 场景时长小于min_duration
        3. 合并后不超过15秒
        
        这样可以减少TTS生成的碎片，让语音更连贯
        """
        if not scenes or len(scenes) < 2:
            return scenes
        
        merged = []
        current = scenes[0].copy()
        
        for i in range(1, len(scenes)):
            next_scene = scenes[i]
            current_duration = current['end_time'] - current['start_time']
            next_duration = next_scene['end_time'] - next_scene['start_time']
            
            # 检查是否可以合并
            can_merge = (
                current.get('audio_mode') == next_scene.get('audio_mode') and
                (current_duration < min_duration or next_duration < min_duration) and
                current_duration + next_duration <= 15.0  # 合并后不超过15秒
            )
            
            if can_merge:
                # 合并场景
                current['end_time'] = next_scene['end_time']
                
                # 合并对话
                if current.get('dialogue') and next_scene.get('dialogue'):
                    current['dialogue'] = current['dialogue'] + ' ' + next_scene['dialogue']
                elif next_scene.get('dialogue'):
                    current['dialogue'] = next_scene['dialogue']
                
                # 合并解说（如果是voiceover模式）
                if current.get('audio_mode') == 'voiceover':
                    if current.get('narration') and next_scene.get('narration'):
                        current['narration'] = current['narration'] + '，' + next_scene['narration']
                    elif next_scene.get('narration'):
                        current['narration'] = next_scene['narration']
                
                # 取最高重要性
                current['importance'] = max(
                    current.get('importance', 0),
                    next_scene.get('importance', 0)
                )
                
                current['reason'] = current.get('reason', '') + ' (已合并)'
            else:
                # 不能合并，保存当前场景，开始新场景
                merged.append(current)
                current = next_scene.copy()
        
        # 添加最后一个场景
        merged.append(current)
        
        if len(merged) < len(scenes):
            print(f"   [MERGE] 合并短场景: {len(scenes)} -> {len(merged)}")
        
        return merged
    
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
        
        # 2. 合并相邻短场景（减少TTS碎片化）
        selected_scenes = self._merge_short_scenes(selected_scenes)
        
        # 3. 调整解说长度
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
        print(f"   [原声] {orig_count} ({orig_count*100//(orig_count+voice_count+1)}%)")
        print(f"   [解说] {voice_count} ({voice_count*100//(orig_count+voice_count+1)}%)")
        print(f"   [时长] {output_time:.0f}秒")
        
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
        mode = "[O]" if t['audio_mode'] == 'original' else "[V]"
        print(f"  {t['source_start']:.0f}s-{t['source_end']:.0f}s {mode} 重要性:{t['importance']:.1f}")

