# core/smart_duration.py - 智能时长计算
"""
SmartVideoClipper - 智能时长计算器

核心原则：
1. 不硬性限制时长，根据内容决定
2. 保留所有精彩场景
3. 压缩过渡/无意义场景

输出时长 = 精彩场景总时长 + 必要过渡
"""

from typing import List, Dict, Tuple


def calculate_smart_duration(
    scenes: List[Dict],
    min_duration: int = 180,  # 最短3分钟
    max_duration: int = 1200,  # 最长20分钟
) -> Tuple[int, List[Dict]]:
    """
    智能计算最佳输出时长
    
    返回：(建议时长, 筛选后的场景列表)
    """
    print("\n[DURATION] 智能分析最佳时长...")
    
    # 按重要性分类场景
    critical_scenes = []  # 必须保留（高分对话、情感爆发）
    important_scenes = []  # 建议保留（中等重要性）
    optional_scenes = []   # 可选（低重要性过渡）
    
    for scene in scenes:
        importance = scene.get('importance', 0.5)
        dialogue = scene.get('dialogue', '')
        emotion = scene.get('emotion', 'neutral')
        
        # 分类逻辑
        if importance >= 0.8 or emotion in ['angry', 'sad', 'excited']:
            # 高重要性或强情感 → 必须保留
            critical_scenes.append(scene)
        elif importance >= 0.5 or len(dialogue) > 30:
            # 中等重要性或有对话 → 建议保留
            important_scenes.append(scene)
        else:
            # 低重要性 → 可选
            optional_scenes.append(scene)
    
    # 计算各类场景时长
    critical_duration = sum(s['end_time'] - s['start_time'] for s in critical_scenes)
    important_duration = sum(s['end_time'] - s['start_time'] for s in important_scenes)
    optional_duration = sum(s['end_time'] - s['start_time'] for s in optional_scenes)
    
    print(f"   必须保留: {len(critical_scenes)}个场景, {critical_duration:.0f}秒")
    print(f"   建议保留: {len(important_scenes)}个场景, {important_duration:.0f}秒")
    print(f"   可选场景: {len(optional_scenes)}个场景, {optional_duration:.0f}秒")
    
    # 决定最终时长
    # 策略：必须 + 建议 + 部分可选（如果还有空间）
    
    selected_scenes = critical_scenes.copy()
    current_duration = critical_duration
    
    # 添加建议场景
    for scene in important_scenes:
        scene_duration = scene['end_time'] - scene['start_time']
        if current_duration + scene_duration <= max_duration:
            selected_scenes.append(scene)
            current_duration += scene_duration
    
    # 如果还不够最短时长，添加可选场景
    if current_duration < min_duration:
        for scene in optional_scenes:
            scene_duration = scene['end_time'] - scene['start_time']
            if current_duration + scene_duration <= max_duration:
                selected_scenes.append(scene)
                current_duration += scene_duration
            if current_duration >= min_duration:
                break
    
    # 按时间排序
    selected_scenes.sort(key=lambda x: x['start_time'])
    
    # 确保在合理范围内
    final_duration = max(min_duration, min(current_duration, max_duration))
    
    print(f"\n   📊 智能建议时长: {final_duration:.0f}秒 ({final_duration/60:.1f}分钟)")
    print(f"   选择场景: {len(selected_scenes)}个")
    
    return int(final_duration), selected_scenes


def decide_audio_mode(scene: Dict) -> str:
    """
    决定场景使用原声还是解说
    
    返回: 'original' 或 'voiceover'
    
    原声场景：
    - 精彩对话（有情感）
    - 动作场面
    - 音乐/歌曲
    - 重要台词
    
    解说场景：
    - 过渡画面
    - 需要背景解释
    - 对话不重要
    """
    dialogue = scene.get('dialogue', '')
    emotion = scene.get('emotion', 'neutral')
    scene_type = scene.get('scene_type', 'unknown')
    importance = scene.get('importance', 0.5)
    
    # 强情感 → 原声
    if emotion in ['angry', 'sad', 'excited', 'happy']:
        return 'original'
    
    # 动作场面 → 原声
    if scene_type == 'action':
        return 'original'
    
    # 有重要对话（长度>20字）→ 原声
    if len(dialogue) > 20 and importance >= 0.6:
        return 'original'
    
    # 高重要性 → 原声
    if importance >= 0.75:
        return 'original'
    
    # 其他 → 解说
    return 'voiceover'


def create_mixed_timeline(
    scenes: List[Dict],
    target_duration: int = None
) -> List[Dict]:
    """
    创建原声/解说混合时间线
    
    确保：
    1. 原声和解说交替出现
    2. 不会连续太长解说
    3. 精彩场景保留原声
    """
    if not scenes:
        return []
    
    # 如果没有指定时长，使用智能计算
    if target_duration is None:
        target_duration, scenes = calculate_smart_duration(scenes)
    
    timeline = []
    output_time = 0
    
    voiceover_count = 0
    original_count = 0
    
    for scene in scenes:
        # 决定音频模式
        audio_mode = decide_audio_mode(scene)
        
        # 防止连续太多解说（最多3个连续解说后强制原声）
        consecutive_voiceover = sum(1 for t in timeline[-3:] if t.get('audio_mode') == 'voiceover')
        if consecutive_voiceover >= 3 and audio_mode == 'voiceover':
            # 如果场景有对话，强制使用原声
            if scene.get('dialogue'):
                audio_mode = 'original'
        
        scene_duration = scene['end_time'] - scene['start_time']
        
        # 添加到时间线
        item = {
            'scene_id': scene.get('scene_id', len(timeline) + 1),
            'source_start': scene['start_time'],
            'source_end': scene['end_time'],
            'output_start': output_time,
            'output_end': output_time + scene_duration,
            'audio_mode': audio_mode,
            'dialogue': scene.get('dialogue', '')[:50],
            'narration': scene.get('narration', ''),
            'emotion': scene.get('emotion', 'neutral'),
        }
        
        timeline.append(item)
        output_time += scene_duration
        
        if audio_mode == 'original':
            original_count += 1
        else:
            voiceover_count += 1
    
    print(f"\n   📋 时间线生成完成:")
    print(f"      原声场景: {original_count} ({original_count*100//(original_count+voiceover_count) if (original_count+voiceover_count) > 0 else 0}%)")
    print(f"      解说场景: {voiceover_count} ({voiceover_count*100//(original_count+voiceover_count) if (original_count+voiceover_count) > 0 else 0}%)")
    print(f"      总时长: {output_time:.0f}秒")
    
    return timeline


# 测试
if __name__ == "__main__":
    # 模拟场景数据
    test_scenes = [
        {'start_time': 0, 'end_time': 30, 'importance': 0.9, 'dialogue': '你是谁？你来这里干什么？', 'emotion': 'angry'},
        {'start_time': 30, 'end_time': 45, 'importance': 0.3, 'dialogue': '', 'emotion': 'neutral'},
        {'start_time': 45, 'end_time': 90, 'importance': 0.8, 'dialogue': '我要告诉你一个秘密', 'emotion': 'sad'},
        {'start_time': 90, 'end_time': 120, 'importance': 0.5, 'dialogue': '好的', 'emotion': 'neutral'},
    ]
    
    duration, selected = calculate_smart_duration(test_scenes)
    timeline = create_mixed_timeline(selected)
    
    for item in timeline:
        mode = "🔊原声" if item['audio_mode'] == 'original' else "🎙️解说"
        print(f"  {item['source_start']:.0f}s-{item['source_end']:.0f}s: {mode}")

