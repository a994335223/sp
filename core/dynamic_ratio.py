# core/dynamic_ratio.py - 动态解说比例计算器 v5.7
"""
SmartVideoClipper - 动态解说比例计算器 v5.7

v5.7核心改进：
1. 废除固定目标比例！改用场景级别智能判断
2. 每个场景独立决定是否需要解说
3. 精彩对白/名台词/强情感 → 100%保留原声
4. 过渡/复杂剧情/无对白 → 100%使用解说

设计原则（v5.7）：
- 精彩对白必须保留原声
- 演员演技场景必须保留原声
- 剧情推进可用解说概括
- 无对白场景用解说填充
- 不再追求固定比例！
"""

import sys
from typing import List, Dict, Tuple
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def log(msg: str):
    """统一日志输出"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class DynamicRatioCalculator:
    """
    动态解说比例计算器 v5.6
    
    职责：
    1. 分析场景特征
    2. 计算全局最优解说比例
    3. 支持场景级别微调
    """
    
    # 比例范围
    MIN_RATIO = 0.30  # 最低30%解说
    MAX_RATIO = 0.75  # 最高75%解说
    BASE_RATIO = 0.55  # 基础55%
    
    # 特征阈值
    DIALOGUE_THRESHOLD_HIGH = 0.6  # 高对话密度
    DIALOGUE_THRESHOLD_MID = 0.4   # 中对话密度
    ACTION_THRESHOLD_HIGH = 0.4    # 高动作占比
    ACTION_THRESHOLD_MID = 0.2     # 中动作占比
    EMOTION_THRESHOLD = 0.3        # 情感场景阈值
    
    def __init__(self, media_type: str = "tv"):
        """
        初始化计算器
        
        参数：
            media_type: 媒体类型 (tv/movie)
        """
        self.media_type = media_type
        
        # 媒体类型基础调整
        if media_type == "tv":
            self.base_ratio = 0.55  # 电视剧默认55%解说
        else:
            self.base_ratio = 0.45  # 电影默认45%解说（更多保留原声）
    
    def calculate_global_ratio(self, scenes: List[Dict]) -> Tuple[float, Dict]:
        """
        计算全局解说比例
        
        参数：
            scenes: 场景列表，需要包含：
                - dialogue: 对话文本
                - emotion: 情感
                - importance: 重要性
                - scene_type: 场景类型（可选）
        
        返回：(推荐比例, 分析详情)
        """
        if not scenes:
            return self.base_ratio, {'reason': '无场景数据'}
        
        total = len(scenes)
        
        # ========== 分析对话密度 ==========
        dialogue_count = 0
        total_dialogue_chars = 0
        for s in scenes:
            dialogue = s.get('dialogue', '').strip()
            if dialogue and len(dialogue) > 10:
                dialogue_count += 1
                total_dialogue_chars += len(dialogue)
        
        dialogue_density = dialogue_count / total
        avg_dialogue_length = total_dialogue_chars / dialogue_count if dialogue_count > 0 else 0
        
        # ========== 分析动作场景 ==========
        # 通过场景类型或无对话+高重要性判断
        action_count = 0
        for s in scenes:
            scene_type = s.get('scene_type', '').lower()
            dialogue = s.get('dialogue', '').strip()
            importance = s.get('importance', 0.5)
            
            if 'action' in scene_type or 'fight' in scene_type:
                action_count += 1
            elif not dialogue and importance > 0.6:
                # 无对话但重要 → 可能是动作场景
                action_count += 0.5
        
        action_density = action_count / total
        
        # ========== 分析情感场景 ==========
        strong_emotions = ['angry', 'sad', 'excited', 'crying', 'shouting']
        emotion_count = sum(1 for s in scenes if s.get('emotion', '') in strong_emotions)
        emotion_density = emotion_count / total
        
        # ========== 分析高重要性场景 ==========
        high_importance_count = sum(1 for s in scenes if s.get('importance', 0) >= 0.7)
        high_importance_density = high_importance_count / total
        
        # ========== 计算比例 ==========
        ratio = self.base_ratio
        adjustments = []
        
        # 对话密度调整
        if dialogue_density > self.DIALOGUE_THRESHOLD_HIGH:
            adjustment = -0.15
            ratio += adjustment
            adjustments.append(f"高对话密度({dialogue_density:.0%}):{adjustment:+.0%}")
        elif dialogue_density > self.DIALOGUE_THRESHOLD_MID:
            adjustment = -0.08
            ratio += adjustment
            adjustments.append(f"中对话密度({dialogue_density:.0%}):{adjustment:+.0%}")
        elif dialogue_density < 0.2:
            adjustment = +0.10
            ratio += adjustment
            adjustments.append(f"低对话密度({dialogue_density:.0%}):{adjustment:+.0%}")
        
        # 对话长度调整
        if avg_dialogue_length > 50:
            adjustment = -0.05
            ratio += adjustment
            adjustments.append(f"长对话({avg_dialogue_length:.0f}字):{adjustment:+.0%}")
        
        # 动作场景调整
        if action_density > self.ACTION_THRESHOLD_HIGH:
            adjustment = +0.15
            ratio += adjustment
            adjustments.append(f"多动作({action_density:.0%}):{adjustment:+.0%}")
        elif action_density > self.ACTION_THRESHOLD_MID:
            adjustment = +0.08
            ratio += adjustment
            adjustments.append(f"中动作({action_density:.0%}):{adjustment:+.0%}")
        
        # 情感场景调整
        if emotion_density > self.EMOTION_THRESHOLD:
            adjustment = -0.08
            ratio += adjustment
            adjustments.append(f"强情感({emotion_density:.0%}):{adjustment:+.0%}")
        
        # 高重要性调整
        if high_importance_density > 0.4:
            adjustment = -0.05
            ratio += adjustment
            adjustments.append(f"多重要场景({high_importance_density:.0%}):{adjustment:+.0%}")
        
        # 限制范围
        ratio = max(self.MIN_RATIO, min(self.MAX_RATIO, ratio))
        
        # 构建分析详情
        details = {
            'base_ratio': self.base_ratio,
            'final_ratio': ratio,
            'dialogue_density': dialogue_density,
            'avg_dialogue_length': avg_dialogue_length,
            'action_density': action_density,
            'emotion_density': emotion_density,
            'high_importance_density': high_importance_density,
            'adjustments': adjustments,
        }
        
        return ratio, details
    
    def get_scene_ratio(
        self,
        scene: Dict,
        global_ratio: float
    ) -> float:
        """
        获取单个场景的解说比例（是否应该用解说）
        
        参数：
            scene: 场景信息
            global_ratio: 全局比例
        
        返回：0.0表示原声，1.0表示解说，0.5表示随机
        """
        dialogue = scene.get('dialogue', '').strip()
        emotion = scene.get('emotion', 'neutral')
        importance = scene.get('importance', 0.5)
        
        # 极高重要性 + 有长对话 → 原声
        if importance >= 0.85 and dialogue and len(dialogue) > 30:
            return 0.0
        
        # 强情感 + 高重要性 → 原声
        if emotion in ['angry', 'sad', 'excited'] and importance >= 0.7:
            return 0.0
        
        # 低重要性 + 无对话 → 解说（或跳过）
        if importance < 0.2 and not dialogue:
            return 1.0
        
        # 有对话但不是关键 → 解说
        if dialogue and len(dialogue) > 5 and importance < 0.7:
            return 1.0
        
        # 无对话但有意义 → 解说
        if not dialogue and importance >= 0.3:
            return 1.0
        
        # 其他情况：根据全局比例决定
        return global_ratio
    
    def print_analysis(self, ratio: float, details: Dict):
        """打印分析结果"""
        log(f"[Ratio] ========== 动态比例分析 v5.6 ==========")
        log(f"[Ratio] 媒体类型: {'电视剧' if self.media_type == 'tv' else '电影'}")
        log(f"[Ratio] 基础比例: {details['base_ratio']*100:.0f}%")
        log(f"[Ratio] 对话密度: {details['dialogue_density']*100:.0f}% (平均{details['avg_dialogue_length']:.0f}字)")
        log(f"[Ratio] 动作占比: {details['action_density']*100:.0f}%")
        log(f"[Ratio] 情感占比: {details['emotion_density']*100:.0f}%")
        log(f"[Ratio] 重要场景: {details['high_importance_density']*100:.0f}%")
        
        if details['adjustments']:
            log(f"[Ratio] 调整项:")
            for adj in details['adjustments']:
                log(f"[Ratio]   - {adj}")
        
        log(f"[Ratio] 最终比例: {ratio*100:.0f}%")
        log(f"[Ratio] ========================================")


def calculate_optimal_ratio(
    scenes: List[Dict],
    media_type: str = "tv"
) -> Tuple[float, Dict]:
    """
    便捷函数：计算最优解说比例
    
    参数：
        scenes: 场景列表
        media_type: 媒体类型
    
    返回：(推荐比例, 分析详情)
    """
    calculator = DynamicRatioCalculator(media_type)
    return calculator.calculate_global_ratio(scenes)


def should_use_narration_v57(scene: Dict) -> Tuple[bool, str]:
    """
    v5.7：智能判断场景是否需要解说（废除固定比例）
    
    核心原则：
    1. 精彩对白 → 原声
    2. 强情感/演技场景 → 原声
    3. 过渡/背景 → 解说
    4. 无对白 → 解说
    
    返回：(是否使用解说, 原因)
    """
    dialogue = scene.get('dialogue', '').strip()
    emotion = scene.get('emotion', 'neutral')
    importance = scene.get('importance', 0.5)
    scene_type = scene.get('scene_type', '').lower()
    
    # ========== 必须保留原声的情况 ==========
    
    # 1. 高重要性 + 长对话 = 精彩对白
    if importance >= 0.85 and dialogue and len(dialogue) > 40:
        return False, "精彩对白必须保留原声"
    
    # 2. 强情感场景 = 演技展示
    if emotion in ['angry', 'crying', 'excited', 'sad'] and importance >= 0.75:
        return False, f"强情感场景({emotion})保留原声"
    
    # 3. 有质量的对话（长度适中+重要）
    if dialogue and 30 < len(dialogue) < 100 and importance >= 0.7:
        return False, "有质量的对话保留原声"
    
    # 4. 非常高重要性（如高潮场景）
    if importance >= 0.9:
        return False, "高潮场景保留原声"
    
    # ========== 必须使用解说的情况 ==========
    
    # 5. 无对白场景
    if not dialogue or len(dialogue) < 5:
        return True, "无对白场景需要解说"
    
    # 6. 过渡场景
    if scene_type in ['transition', 'background', 'establishing']:
        return True, "过渡场景使用解说"
    
    # 7. 低重要性场景
    if importance < 0.3:
        return True, "低重要性场景使用解说"
    
    # 8. 对话太长（需要概括）
    if dialogue and len(dialogue) > 150:
        return True, "长对话用解说概括"
    
    # ========== 中间情况：根据特征决定 ==========
    
    # 9. 中等重要性 + 短对话 = 解说
    if importance < 0.6 and dialogue and len(dialogue) < 30:
        return True, "普通对话用解说概括"
    
    # 10. 中等重要性 + 中等对话 = 看情感
    if emotion == 'neutral' and importance < 0.65:
        return True, "平淡场景用解说概括"
    
    # 默认：保留原声
    return False, "默认保留原声"


def classify_scenes_v57(scenes: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    v5.7：对所有场景进行智能分类
    
    返回：(分类后的场景列表, 统计信息)
    """
    original_count = 0
    voiceover_count = 0
    
    for scene in scenes:
        use_narration, reason = should_use_narration_v57(scene)
        scene['v57_use_narration'] = use_narration
        scene['v57_reason'] = reason
        
        if use_narration:
            voiceover_count += 1
        else:
            original_count += 1
    
    total = len(scenes)
    stats = {
        'total': total,
        'original': original_count,
        'voiceover': voiceover_count,
        'original_ratio': original_count / total if total > 0 else 0,
        'voiceover_ratio': voiceover_count / total if total > 0 else 0,
    }
    
    log(f"[Ratio v5.7] ========== 智能场景分类 ==========")
    log(f"[Ratio v5.7] 总场景: {total}")
    log(f"[Ratio v5.7] 原声场景: {original_count} ({stats['original_ratio']*100:.0f}%)")
    log(f"[Ratio v5.7] 解说场景: {voiceover_count} ({stats['voiceover_ratio']*100:.0f}%)")
    log(f"[Ratio v5.7] ================================")
    
    return scenes, stats


# 测试
if __name__ == "__main__":
    # 测试场景1：对话多
    scenes_dialogue_heavy = [
        {'dialogue': '你好，我是张三，今天我们来讨论一下这个问题', 'emotion': 'neutral', 'importance': 0.5},
        {'dialogue': '我认为这个方案可行，但需要更多的考虑', 'emotion': 'neutral', 'importance': 0.6},
        {'dialogue': '对，我同意你的看法', 'emotion': 'neutral', 'importance': 0.4},
    ] * 20
    
    calc = DynamicRatioCalculator("tv")
    ratio1, details1 = calc.calculate_global_ratio(scenes_dialogue_heavy)
    print(f"\n对话多场景 - 推荐比例: {ratio1*100:.0f}%")
    calc.print_analysis(ratio1, details1)
    
    # 测试场景2：动作多
    scenes_action_heavy = [
        {'dialogue': '', 'emotion': 'neutral', 'importance': 0.7, 'scene_type': 'action'},
        {'dialogue': '', 'emotion': 'excited', 'importance': 0.8, 'scene_type': 'fight'},
        {'dialogue': '小心！', 'emotion': 'angry', 'importance': 0.6},
    ] * 20
    
    ratio2, details2 = calc.calculate_global_ratio(scenes_action_heavy)
    print(f"\n动作多场景 - 推荐比例: {ratio2*100:.0f}%")
    calc.print_analysis(ratio2, details2)
    
    # 测试场景3：情感多
    scenes_emotion_heavy = [
        {'dialogue': '我真的很伤心', 'emotion': 'sad', 'importance': 0.8},
        {'dialogue': '你怎么能这样对我！', 'emotion': 'angry', 'importance': 0.9},
        {'dialogue': '', 'emotion': 'crying', 'importance': 0.7},
    ] * 20
    
    ratio3, details3 = calc.calculate_global_ratio(scenes_emotion_heavy)
    print(f"\n情感多场景 - 推荐比例: {ratio3*100:.0f}%")
    calc.print_analysis(ratio3, details3)

