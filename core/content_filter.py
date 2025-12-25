# core/content_filter.py - 内容过滤器
"""
SmartVideoClipper - 内容安全过滤

功能：
1. 过滤政治敏感词
2. 过滤违规内容
3. 过滤低质量内容

必须在任何输出前调用！
"""

import re
from typing import List, Tuple


# 敏感词列表（持续更新）
SENSITIVE_WORDS = [
    # 政治人物
    "习近平", "胡锦涛", "江泽民", "毛泽东", "邓小平", "温家宝", "李克强",
    "习主席", "总书记", "国家主席", "中央领导",
    # 政治术语
    "共产党", "国民党", "民进党", "法轮功", "六四", "天安门",
    "台独", "藏独", "疆独", "港独",
    "反华", "辱华", "颠覆", "分裂",
    # 其他敏感
    "色情", "赌博", "毒品",
]

# 低质量内容模式
LOW_QUALITY_PATTERNS = [
    r"紧张的场面",  # 重复的无意义描述
    r"紧张的一幕出现了",
    r"此刻，紧张",
    r"画面一转，紧张",
    r"未知场景",
    r"unknown",
]

# v5.7新增：广告对白识别模式
AD_PATTERNS = [
    # 药品广告
    r"用痛[﹔;,，]?用经敌",
    r"家中常备",
    r"经敌邀您观看",
    r"邀您观看",
    r"巨颗话谈",
    r"苦红利焉",
    r"精通电子案",
    r"穿被皮发膏",
    r"教您观看",
    # 其他广告
    r"赞助播出",
    r"独家冠名",
    r"为您呈现",
    r"温馨提示",
    r"下期预告",
    # 乱码识别（Whisper乱码特征）
    r"[﹔;]{2,}",  # 连续分号
    r"[\u4e00-\u9fa5]{1,2}[﹔;][\u4e00-\u9fa5]{1,2}[﹔;]",  # 字﹔字﹔模式
]


def is_ad_content(text: str) -> bool:
    """
    v5.7：检查是否是广告内容
    """
    if not text:
        return False
    
    for pattern in AD_PATTERNS:
        if re.search(pattern, text):
            return True
    
    # 检测乱码特征：短词+分号组合过多
    if text.count('﹔') > 3 or text.count(';') > 5:
        return True
    
    return False


def filter_ad_content(text: str) -> Tuple[str, bool]:
    """
    v5.7：过滤广告内容
    
    返回：(过滤后的文本, 是否是广告)
    """
    if is_ad_content(text):
        return "", True
    return text, False


def filter_sensitive_content(text: str) -> Tuple[str, List[str]]:
    """
    过滤敏感内容
    
    返回：(过滤后的文本, 被过滤的词列表)
    """
    filtered_words = []
    result = text
    
    for word in SENSITIVE_WORDS:
        if word in result:
            filtered_words.append(word)
            result = result.replace(word, "***")
    
    return result, filtered_words


def is_low_quality(text: str) -> bool:
    """检查是否是低质量内容"""
    for pattern in LOW_QUALITY_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def filter_narration(narration: str) -> str:
    """
    过滤解说内容
    
    1. 移除敏感词
    2. 检查质量
    """
    # 过滤敏感词
    filtered, removed = filter_sensitive_content(narration)
    
    if removed:
        print(f"   [FILTER] 已过滤敏感词: {removed}")
    
    # 如果内容太短或质量太低，返回空
    if len(filtered.strip()) < 5:
        return ""
    
    if is_low_quality(filtered):
        return ""
    
    return filtered


def filter_transcript(segments: list) -> list:
    """
    过滤字幕内容 v5.7.2（增强版）
    
    过滤内容：
    1. 广告乱码（Whisper识别广告产生的乱码）
    2. 敏感词
    """
    filtered_segments = []
    ad_count = 0
    
    for seg in segments:
        text = seg.get('text', '')
        
        # v5.7.2: 首先检查是否是广告内容
        if is_ad_content(text):
            ad_count += 1
            continue  # 直接跳过广告段落，不加入结果
        
        # 过滤敏感词
        filtered_text, removed = filter_sensitive_content(text)
        
        if removed:
            print(f"   [FILTER] 字幕过滤敏感词: {removed}")
        
        seg['text'] = filtered_text
        filtered_segments.append(seg)
    
    if ad_count > 0:
        print(f"   [FILTER] 已过滤 {ad_count} 条广告/乱码字幕")
    
    return filtered_segments


def validate_output(content: str) -> bool:
    """验证输出内容是否安全"""
    # 检查敏感词
    for word in SENSITIVE_WORDS:
        if word in content:
            return False
    
    return True


# 测试
if __name__ == "__main__":
    test_texts = [
        "今天讲一个关于习近平的故事",
        "这是一个紧张的场面",
        "正常的解说内容",
    ]
    
    for text in test_texts:
        filtered, removed = filter_sensitive_content(text)
        quality = "低质量" if is_low_quality(text) else "正常"
        print(f"原文: {text}")
        print(f"过滤后: {filtered}, 移除: {removed}, 质量: {quality}")
        print()

