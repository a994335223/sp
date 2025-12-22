# core/auto_detect_highlights.py - 自动检测需要保留原声的片段
"""
SmartVideoClipper - 原声保留检测模块

功能: 自动判断哪些片段需要保留原声
用途: 保留经典台词、高潮场景、搞笑片段的原音

依赖: 无额外依赖
"""


def auto_detect_keep_original(segments: list, scene_analysis: list) -> list:
    """
    自动判断哪些片段需要保留原声
    
    判断标准（全自动）:
    1. 经典台词（台词长度适中，语气强烈）
    2. 高潮场景（CLIP检测为打斗/浪漫/悲伤场景）
    3. 搞笑片段（CLIP检测为搞笑场景）
    
    参数:
        segments: 语音识别的字幕列表 [{'start': 0, 'end': 5, 'text': '...'}, ...]
        scene_analysis: CLIP分析的镜头列表 [{'start': 0, 'end': 5, 'scene_type': '...', 'confidence': 0.8}, ...]
    
    返回:
        [{'start': 10, 'end': 20, 'reason': '经典台词', 'text': '...'}, ...]
    """
    keep_original = []
    
    for seg in segments:
        text = seg['text']
        start, end = seg['start'], seg['end']
        duration = end - start
        
        # 查找对应的场景分析
        matching_scene = None
        for scene in scene_analysis:
            if scene['start'] <= start < scene['end']:
                matching_scene = scene
                break
        
        should_keep = False
        reason = ""
        
        # 规则1: 经典台词（5-15秒，包含感叹号或问号）
        if 5 <= duration <= 15 and ('！' in text or '？' in text or '!' in text or '?' in text):
            should_keep = True
            reason = "经典台词"
        
        # 规则2: 高潮场景
        if matching_scene:
            important_types = ['打斗动作场景', '浪漫爱情场景', '悲伤哭泣场景', '搞笑幽默场景']
            if matching_scene.get('scene_type') in important_types and matching_scene.get('confidence', 0) > 0.4:
                should_keep = True
                reason = matching_scene['scene_type']
        
        # 规则3: 包含特定关键词的对话
        keywords = ['我爱你', '对不起', '不要', '救命', '为什么', '怎么可能', '太棒了', '完了']
        for kw in keywords:
            if kw in text:
                should_keep = True
                reason = f"关键词: {kw}"
                break
        
        # 规则4: 长句子（可能是重要独白）
        if len(text) > 50 and duration > 10:
            should_keep = True
            reason = "重要独白"
        
        if should_keep:
            keep_original.append({
                'start': start,
                'end': end,
                'reason': reason,
                'text': text[:30] + ('...' if len(text) > 30 else '')
            })
    
    print(f"[OK] 自动检测到 {len(keep_original)} 个需要保留原声的片段")
    
    # 打印前5个
    for i, item in enumerate(keep_original[:5]):
        print(f"   {i+1}. {item['start']:.1f}s-{item['end']:.1f}s: {item['reason']} - \"{item['text']}\"")
    
    if len(keep_original) > 5:
        print(f"   ... 还有 {len(keep_original) - 5} 个片段")
    
    return keep_original


def merge_adjacent_segments(segments: list, gap_threshold: float = 2.0) -> list:
    """
    合并相邻的原声保留片段
    
    参数:
        segments: 原声保留片段列表
        gap_threshold: 最大间隔（秒），小于此值的相邻片段会被合并
    
    返回:
        合并后的片段列表
    """
    if not segments:
        return []
    
    # 按开始时间排序
    sorted_segs = sorted(segments, key=lambda x: x['start'])
    
    merged = [sorted_segs[0].copy()]
    
    for seg in sorted_segs[1:]:
        last = merged[-1]
        
        # 如果间隔小于阈值，合并
        if seg['start'] - last['end'] <= gap_threshold:
            last['end'] = max(last['end'], seg['end'])
            last['reason'] = f"{last['reason']} + {seg['reason']}"
        else:
            merged.append(seg.copy())
    
    print(f"   合并后剩余 {len(merged)} 个片段")
    return merged


def filter_by_duration(segments: list, min_duration: float = 3.0, max_duration: float = 30.0) -> list:
    """
    按时长过滤片段
    
    参数:
        segments: 原声保留片段列表
        min_duration: 最小时长（秒）
        max_duration: 最大时长（秒）
    
    返回:
        过滤后的片段列表
    """
    filtered = [
        seg for seg in segments
        if min_duration <= (seg['end'] - seg['start']) <= max_duration
    ]
    
    print(f"   过滤后剩余 {len(filtered)} 个片段（{min_duration}s-{max_duration}s）")
    return filtered


# 使用示例
if __name__ == "__main__":
    # 模拟数据
    segments = [
        {'start': 10, 'end': 20, 'text': '你怎么能这样对我！我一直相信你！'},
        {'start': 50, 'end': 55, 'text': '我爱你'},
        {'start': 100, 'end': 115, 'text': '这是一段很长的独白，讲述了主角内心的挣扎和痛苦，以及他对未来的迷茫...'},
        {'start': 200, 'end': 205, 'text': '普通对话'},
    ]
    
    scene_analysis = [
        {'start': 0, 'end': 30, 'scene_type': '悲伤哭泣场景', 'confidence': 0.8},
        {'start': 30, 'end': 60, 'scene_type': '浪漫爱情场景', 'confidence': 0.7},
        {'start': 90, 'end': 120, 'scene_type': '两人对话场景', 'confidence': 0.6},
        {'start': 180, 'end': 210, 'scene_type': '普通过渡镜头', 'confidence': 0.5},
    ]
    
    print("测试自动检测保留原声片段:")
    print("=" * 50)
    
    keep_original = auto_detect_keep_original(segments, scene_analysis)
    
    print("\n合并相邻片段:")
    merged = merge_adjacent_segments(keep_original)
    
    print("\n按时长过滤:")
    filtered = filter_by_duration(merged)
