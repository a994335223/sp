# core/smart_importance.py - 智能重要性评分系统
"""
SmartVideoClipper - 视频重要性评分模块

核心功能：多维度分析视频片段的重要性
- 音频能量分析：高能量=重要（动作/冲突场景）
- 对话密度分析：对白多=剧情关键
- 情感波动分析：情感变化大=高潮
- 人脸/人物分析：主角镜头更重要
- 场景变化率：快速切换=紧张/动作

参考研究：
- Video Summarization with Attention (arxiv:1904.10669)
- 国标：片头≤90秒，片尾≤180秒，正片≥41分钟
"""

import cv2
import numpy as np
import subprocess
import os
import json
from typing import List, Dict, Tuple
from pathlib import Path


def extract_audio_energy(video_path: str, output_dir: str) -> List[Dict]:
    """
    提取音频能量曲线
    高能量片段通常是：动作场景、冲突对话、背景音乐高潮
    """
    print("[AUDIO] 分析音频能量...")
    
    os.makedirs(output_dir, exist_ok=True)
    audio_file = os.path.join(output_dir, "temp_audio.wav")
    
    # 提取音频
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        '-loglevel', 'error',
        audio_file
    ]
    subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    if not os.path.exists(audio_file):
        print("   [WARNING] 音频提取失败")
        return []
    
    # 分析音频能量（使用ffprobe的volumedetect）
    energy_data = []
    
    try:
        # 获取视频时长
        duration_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(duration_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        total_duration = float(result.stdout.strip())
        
        # 每5秒分析一次音频能量
        interval = 5
        for start in range(0, int(total_duration), interval):
            # 使用ffmpeg分析这段的音量
            vol_cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', audio_file,
                '-t', str(interval),
                '-af', 'volumedetect',
                '-f', 'null', '-'
            ]
            result = subprocess.run(vol_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # 解析平均音量
            mean_volume = -50  # 默认静音
            for line in result.stderr.split('\n'):
                if 'mean_volume' in line:
                    try:
                        mean_volume = float(line.split(':')[1].strip().replace(' dB', ''))
                    except:
                        pass
            
            # 转换为0-1的能量值（-60dB到0dB映射到0-1）
            energy = max(0, min(1, (mean_volume + 60) / 60))
            
            energy_data.append({
                'start': start,
                'end': min(start + interval, total_duration),
                'energy': energy,
                'volume_db': mean_volume
            })
        
        print(f"   分析了 {len(energy_data)} 个音频片段")
        
    except Exception as e:
        print(f"   [WARNING] 音频能量分析失败: {e}")
    
    # 清理临时文件
    try:
        os.remove(audio_file)
    except:
        pass
    
    return energy_data


def analyze_dialogue_density(segments: List[Dict], duration: float) -> List[Dict]:
    """
    分析对话密度
    对白密集的片段通常是重要剧情
    """
    print("[DIALOGUE] 分析对话密度...")
    
    if not segments:
        return []
    
    # 每10秒统计对白数量
    interval = 10
    density_data = []
    
    for start in range(0, int(duration), interval):
        end = min(start + interval, duration)
        
        # 统计这个时间段内的对白
        dialogue_count = 0
        dialogue_chars = 0
        
        for seg in segments:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)
            
            # 检查是否在当前时间段内
            if seg_start < end and seg_end > start:
                dialogue_count += 1
                dialogue_chars += len(seg.get('text', ''))
        
        # 计算密度分数（归一化到0-1）
        density = min(1, dialogue_count / 5)  # 假设每10秒5句对白是高密度
        
        density_data.append({
            'start': start,
            'end': end,
            'dialogue_count': dialogue_count,
            'dialogue_chars': dialogue_chars,
            'density': density
        })
    
    print(f"   分析了 {len(density_data)} 个对话片段")
    return density_data


def analyze_scene_change_rate(scenes: List[Dict]) -> List[Dict]:
    """
    分析场景变化率
    快速切换=紧张/动作场景
    """
    print("[SCENE] 分析场景变化率...")
    
    if not scenes or len(scenes) < 2:
        return []
    
    # 计算每个场景的切换频率
    change_data = []
    
    # 统计每30秒内的场景切换次数
    interval = 30
    total_duration = scenes[-1].get('end', 0) if scenes else 0
    
    for start in range(0, int(total_duration), interval):
        end = min(start + interval, total_duration)
        
        # 统计这个时间段内的场景数
        scene_count = 0
        for scene in scenes:
            scene_start = scene.get('start', 0)
            if start <= scene_start < end:
                scene_count += 1
        
        # 计算变化率分数（假设每30秒10个场景是高变化率）
        rate = min(1, scene_count / 10)
        
        change_data.append({
            'start': start,
            'end': end,
            'scene_count': scene_count,
            'change_rate': rate
        })
    
    print(f"   分析了 {len(change_data)} 个场景变化片段")
    return change_data


def detect_emotional_keywords(transcript_segments: List[Dict]) -> List[Dict]:
    """
    检测情感关键词
    包含特定关键词的对白片段通常是高潮
    """
    print("[EMOTION] 检测情感关键词...")
    
    # 情感关键词（中文）
    emotional_keywords = {
        'high': ['杀', '死', '爱', '恨', '救', '跑', '快', '危险', '完了', '不行', 
                 '为什么', '怎么', '不要', '求求', '对不起', '原谅', '真相', '秘密',
                 '发现', '知道了', '抓住', '放开', '住手', '冷静', '相信'],
        'medium': ['重要', '必须', '一定', '绝对', '永远', '从来', '突然', '马上',
                   '立刻', '终于', '原来', '其实', '没想到', '不可能', '怎么办'],
        'low': ['好', '行', '可以', '知道', '明白', '是的', '对', '嗯']
    }
    
    emotional_segments = []
    
    for seg in transcript_segments:
        text = seg.get('text', '')
        start = seg.get('start', 0)
        end = seg.get('end', 0)
        
        # 计算情感分数
        score = 0
        found_keywords = []
        
        for kw in emotional_keywords['high']:
            if kw in text:
                score += 1.0
                found_keywords.append(kw)
        
        for kw in emotional_keywords['medium']:
            if kw in text:
                score += 0.5
                found_keywords.append(kw)
        
        if score > 0:
            emotional_segments.append({
                'start': start,
                'end': end,
                'text': text,
                'emotion_score': min(1, score / 3),  # 归一化
                'keywords': found_keywords
            })
    
    print(f"   检测到 {len(emotional_segments)} 个情感片段")
    return emotional_segments


def calculate_importance_scores(
    video_path: str,
    scenes: List[Dict],
    transcript_segments: List[Dict],
    work_dir: str
) -> List[Dict]:
    """
    计算综合重要性分数
    
    权重分配：
    - 音频能量: 25% （动作/冲突）
    - 对话密度: 25% （剧情关键）
    - 情感关键词: 30% （高潮时刻）
    - 场景变化率: 20% （紧张节奏）
    """
    print("\n[IMPORTANCE] 开始计算视频重要性分数...")
    
    # 获取视频时长
    duration_cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    total_duration = float(result.stdout.strip()) if result.stdout.strip() else 0
    
    if total_duration == 0:
        print("   [ERROR] 无法获取视频时长")
        return scenes
    
    # 1. 音频能量分析
    audio_energy = extract_audio_energy(video_path, work_dir)
    
    # 2. 对话密度分析
    dialogue_density = analyze_dialogue_density(transcript_segments, total_duration)
    
    # 3. 场景变化率分析
    scene_change = analyze_scene_change_rate(scenes)
    
    # 4. 情感关键词检测
    emotional_segments = detect_emotional_keywords(transcript_segments)
    
    # 为每个场景计算综合分数
    print("[SCORE] 计算综合重要性分数...")
    
    for scene in scenes:
        scene_start = scene.get('start', 0)
        scene_end = scene.get('end', 0)
        scene_mid = (scene_start + scene_end) / 2
        
        # 音频能量分数
        audio_score = 0
        for ae in audio_energy:
            if ae['start'] <= scene_mid < ae['end']:
                audio_score = ae['energy']
                break
        
        # 对话密度分数
        dialogue_score = 0
        for dd in dialogue_density:
            if dd['start'] <= scene_mid < dd['end']:
                dialogue_score = dd['density']
                break
        
        # 场景变化率分数
        change_score = 0
        for sc in scene_change:
            if sc['start'] <= scene_mid < sc['end']:
                change_score = sc['change_rate']
                break
        
        # 情感关键词分数
        emotion_score = 0
        for es in emotional_segments:
            if es['start'] <= scene_end and es['end'] >= scene_start:
                emotion_score = max(emotion_score, es['emotion_score'])
        
        # 综合分数（加权平均）
        importance = (
            audio_score * 0.25 +
            dialogue_score * 0.25 +
            emotion_score * 0.30 +
            change_score * 0.20
        )
        
        # 更新场景信息
        scene['audio_score'] = round(audio_score, 3)
        scene['dialogue_score'] = round(dialogue_score, 3)
        scene['emotion_score'] = round(emotion_score, 3)
        scene['change_score'] = round(change_score, 3)
        scene['importance'] = round(importance, 3)
        scene['is_important'] = importance > 0.4  # 阈值
    
    # 统计重要场景
    important_count = sum(1 for s in scenes if s.get('is_important', False))
    print(f"[OK] 计算完成，发现 {important_count} 个重要场景（共{len(scenes)}个）")
    
    # 打印top10重要场景
    sorted_scenes = sorted(scenes, key=lambda x: x.get('importance', 0), reverse=True)
    print("\n[TOP10] 最重要的场景:")
    for i, s in enumerate(sorted_scenes[:10]):
        print(f"   {i+1}. {s['start']:.0f}s-{s['end']:.0f}s 重要性:{s['importance']:.2f} "
              f"(音频:{s['audio_score']:.2f} 对话:{s['dialogue_score']:.2f} "
              f"情感:{s['emotion_score']:.2f} 变化:{s['change_score']:.2f})")
    
    return scenes


def select_important_clips(
    scenes: List[Dict],
    target_duration: int,
    min_clip_duration: float = 2.0,
    max_clip_duration: float = 30.0
) -> List[Dict]:
    """
    基于重要性分数选择片段
    
    策略：
    1. 按重要性排序
    2. 优先选择高分场景
    3. 确保时间分布均匀（不全集中在开头或结尾）
    4. 合并相邻的重要场景
    """
    print(f"\n[SELECT] 选择重要片段 (目标: {target_duration}秒)...")
    
    if not scenes:
        return []
    
    # 按重要性排序
    sorted_scenes = sorted(scenes, key=lambda x: x.get('importance', 0), reverse=True)
    
    selected = []
    total_duration = 0
    used_ranges = []  # 记录已选择的时间范围
    
    # 将视频分成几个时间段，确保每个段都有内容
    total_video_duration = max(s.get('end', 0) for s in scenes)
    num_segments = 5  # 分成5段
    segment_duration = total_video_duration / num_segments
    segment_quotas = [target_duration / num_segments] * num_segments  # 每段配额
    
    for scene in sorted_scenes:
        if total_duration >= target_duration:
            break
        
        scene_start = scene.get('start', 0)
        scene_end = scene.get('end', 0)
        scene_duration = scene_end - scene_start
        
        # 跳过太短或太长的片段
        if scene_duration < min_clip_duration:
            continue
        if scene_duration > max_clip_duration:
            # 截取中间部分
            mid = (scene_start + scene_end) / 2
            scene_start = mid - max_clip_duration / 2
            scene_end = mid + max_clip_duration / 2
            scene_duration = max_clip_duration
        
        # 检查是否与已选片段重叠
        overlap = False
        for used_start, used_end in used_ranges:
            if not (scene_end <= used_start or scene_start >= used_end):
                overlap = True
                break
        
        if overlap:
            continue
        
        # 检查所属时间段的配额
        segment_idx = min(int(scene_start / segment_duration), num_segments - 1)
        if segment_quotas[segment_idx] <= 0:
            continue  # 这个时间段已经满了
        
        # 选择这个场景
        selected.append({
            'start': scene_start,
            'end': scene_end,
            'importance': scene.get('importance', 0),
            'duration': scene_duration
        })
        
        used_ranges.append((scene_start, scene_end))
        total_duration += scene_duration
        segment_quotas[segment_idx] -= scene_duration
    
    # 按时间排序
    selected = sorted(selected, key=lambda x: x['start'])
    
    print(f"[OK] 选择了 {len(selected)} 个片段，总时长 {total_duration:.0f}秒")
    
    return selected


def calculate_scene_importance(
    dialogue: str,
    duration: float,
    emotion: str = 'neutral'
) -> float:
    """
    计算单个场景的重要性分数
    
    简化版本，用于快速评估
    
    参数：
        dialogue: 场景对话内容
        duration: 场景时长
        emotion: 情感类型
    
    返回：
        0-1 的重要性分数
    """
    score = 0.3  # 基础分
    
    # 1. 对话长度加分（有对话更重要）
    if dialogue:
        dialogue_len = len(dialogue)
        if dialogue_len > 50:
            score += 0.3
        elif dialogue_len > 20:
            score += 0.2
        elif dialogue_len > 5:
            score += 0.1
    
    # 2. 情感加分
    emotion_weights = {
        'angry': 0.3,
        'sad': 0.25,
        'excited': 0.3,
        'happy': 0.2,
        'fear': 0.25,
        'neutral': 0
    }
    score += emotion_weights.get(emotion, 0)
    
    # 3. 情感关键词加分
    high_keywords = ['杀', '死', '爱', '恨', '救', '跑', '危险', '完了', '为什么', 
                     '不要', '求求', '对不起', '真相', '秘密', '发现', '知道了']
    medium_keywords = ['重要', '必须', '一定', '绝对', '突然', '终于', '原来', '不可能']
    
    if dialogue:
        for kw in high_keywords:
            if kw in dialogue:
                score += 0.1
                break
        for kw in medium_keywords:
            if kw in dialogue:
                score += 0.05
                break
    
    # 4. 时长调整（太短或太长的扣分）
    if duration < 2:
        score -= 0.1
    elif duration > 60:
        score -= 0.1
    
    # 确保在0-1范围内
    return max(0, min(1, score))


# 测试
if __name__ == "__main__":
    print("智能重要性评分模块测试")
    print("使用方法: 在main_auto.py中调用 calculate_importance_scores()")
    
    # 测试 calculate_scene_importance
    test_cases = [
        ("你为什么要杀我？我不要死！", 10, "angry"),
        ("好的，我知道了。", 5, "neutral"),
        ("", 3, "neutral"),
        ("这是一个关于爱与恨的真相", 15, "sad"),
    ]
    
    print("\ncalculate_scene_importance 测试:")
    for dialogue, duration, emotion in test_cases:
        score = calculate_scene_importance(dialogue, duration, emotion)
        print(f"  对话: '{dialogue[:20]}...' 时长:{duration}s 情感:{emotion} => 分数:{score:.2f}")

