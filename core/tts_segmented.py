# core/tts_segmented.py - 分段TTS合成器 v5.1
"""
SmartVideoClipper - 分段语音合成 (已优化停顿问题)

核心原则：
每个解说场景单独生成一个音频文件！

v5.1 改进：
1. 修复语音停顿问题（优化标点符号处理）
2. 短文本合并，避免碎片化
3. 语速更稳定，更自然
"""

import os
import re
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class SegmentedTTS:
    """
    分段TTS合成器 v5.1
    
    每个解说场景生成独立的音频文件
    """
    
    def __init__(self, voice: str = "zh-CN-YunxiNeural"):
        """
        初始化
        
        voice: Edge-TTS 语音
            - zh-CN-YunxiNeural (男声，推荐，语速稳定)
            - zh-CN-XiaoxiaoNeural (女声)
            - zh-CN-YunyangNeural (男声，新闻风格，语速较快)
        """
        self.voice = voice
        self.rate = "-5%"  # 稍慢一点，减少停顿感
        
        print(f"[TTS] 分段合成器 v5.1 初始化")
        print(f"      语音: {voice}")
        print(f"      语速: {self.rate}")
    
    def _optimize_text_for_tts(self, text: str) -> str:
        """
        优化文本，减少TTS停顿问题
        
        1. 移除多余的标点
        2. 替换会导致长停顿的标点
        3. 确保句子完整流畅
        """
        if not text:
            return ""
        
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 替换省略号为逗号（避免长停顿）
        text = text.replace('...', '，')
        text = text.replace('…', '，')
        
        # 移除连续标点
        text = re.sub(r'[，。！？]{2,}', '，', text)
        
        # 句子太短？补充完整
        if len(text) < 8 and not text.endswith(('。', '！', '？')):
            text = text.rstrip('，、') + '。'
        
        # 确保以标点结尾
        if text and text[-1] not in '。！？，':
            text += '。'
        
        return text
    
    async def synthesize_segments(
        self,
        segments: List[Dict],
        output_dir: str,
        target_durations: List[float] = None
    ) -> List[Dict]:
        """
        为每个解说段落生成音频
        
        参数：
            segments: 解说段落列表，每项包含 {'text': '解说文本', 'scene_id': 1}
            output_dir: 输出目录
            target_durations: 目标时长列表（用于调速）
        
        返回：
            音频信息列表，每项包含 {'audio_path': '...', 'duration': 5.2, 'scene_id': 1}
        """
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n[TTS] 开始分段合成 {len(segments)} 个片段...")
        
        results = []
        
        for i, seg in enumerate(segments):
            text = seg.get('text', '').strip()
            scene_id = seg.get('scene_id', i + 1)
            
            if not text:
                continue
            
            # 输出路径
            audio_path = os.path.join(output_dir, f"narration_{scene_id:04d}.wav")
            
            # 目标时长（如果有）
            target_duration = None
            if target_durations and i < len(target_durations):
                target_duration = target_durations[i]
            
            # 合成音频
            success, duration = await self._synthesize_single(
                text, audio_path, target_duration
            )
            
            if success:
                results.append({
                    'audio_path': audio_path,
                    'duration': duration,
                    'scene_id': scene_id,
                    'text': text,
                    'start': 0,  # 音频起始位置
                })
            
            # 进度
            if (i + 1) % 5 == 0 or i == len(segments) - 1:
                print(f"   进度: {i+1}/{len(segments)}")
        
        total_duration = sum(r['duration'] for r in results)
        print(f"[OK] TTS分段合成完成: {len(results)}个, 总时长{total_duration:.1f}秒")
        
        return results
    
    async def _synthesize_single(
        self,
        text: str,
        output_path: str,
        target_duration: float = None,
        max_retries: int = 3
    ) -> Tuple[bool, float]:
        """
        合成单个音频（带重试机制）
        
        返回：(是否成功, 实际时长)
        """
        try:
            import edge_tts
            
            # 优化文本，减少停顿
            optimized_text = self._optimize_text_for_tts(text)
            if not optimized_text:
                return False, 0
            
            temp_path = output_path + '.temp.mp3'
            
            # 重试机制
            success = False
            for attempt in range(max_retries):
                try:
                    communicate = edge_tts.Communicate(optimized_text, self.voice, rate=self.rate)
                    await communicate.save(temp_path)
                    
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                        success = True
                        break  # 成功
                        
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"   [RETRY] TTS第{attempt+1}次失败，重试中...")
                        await asyncio.sleep(1)  # 等待1秒后重试
                    else:
                        print(f"   [ERROR] TTS合成失败(已重试{max_retries}次): {e}")
            
            if not success or not os.path.exists(temp_path):
                return False, 0
            
            # 转换为wav并获取时长
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_path,
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                '-loglevel', 'error',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            
            # 获取时长
            duration = self._get_audio_duration(output_path)
            
            # 如果有目标时长，进行调速
            if target_duration and duration > 0:
                speed_ratio = duration / target_duration
                
                # 只在差异较大时调速（避免过度变形）
                if speed_ratio > 1.3 or speed_ratio < 0.7:
                    # 调速
                    adjusted_path = output_path + '.adjusted.wav'
                    self._adjust_speed(output_path, adjusted_path, speed_ratio)
                    
                    if os.path.exists(adjusted_path):
                        os.replace(adjusted_path, output_path)
                        duration = self._get_audio_duration(output_path)
            
            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass
            
            return True, duration
            
        except Exception as e:
            print(f"   [ERROR] TTS合成失败: {e}")
            return False, 0
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            return float(result.stdout.strip())
        except:
            return 0
    
    def _adjust_speed(self, input_path: str, output_path: str, speed_ratio: float):
        """调整音频速度"""
        # 限制调速范围
        speed_ratio = max(0.5, min(2.0, speed_ratio))
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-filter:a', f'atempo={speed_ratio}',
            '-loglevel', 'error',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')


async def synthesize_timeline_narrations(
    timeline: List[Dict],
    output_dir: str,
    voice: str = "zh-CN-YunxiNeural"
) -> List[Dict]:
    """
    为时间线中的解说场景生成音频
    
    参数：
        timeline: 时间线，每项需要 audio_mode 和 narration 字段
        output_dir: 输出目录
    
    返回：
        解说音频信息列表
    """
    # 提取需要TTS的段落
    voiceover_segments = []
    target_durations = []
    
    for item in timeline:
        if item.get('audio_mode') == 'voiceover':
            narration = item.get('narration', '').strip()
            if narration:
                voiceover_segments.append({
                    'text': narration,
                    'scene_id': item.get('scene_id', len(voiceover_segments) + 1)
                })
                # 目标时长 = 场景时长
                duration = item.get('source_end', 0) - item.get('source_start', 0)
                target_durations.append(duration)
    
    if not voiceover_segments:
        print("[TTS] 没有需要合成的解说段落")
        return []
    
    # 合成
    tts = SegmentedTTS(voice=voice)
    results = await tts.synthesize_segments(
        voiceover_segments, 
        output_dir,
        target_durations
    )
    
    return results


# 测试
if __name__ == "__main__":
    async def test():
        segments = [
            {'text': '这是第一段解说内容', 'scene_id': 1},
            {'text': '这是第二段解说，稍微长一点', 'scene_id': 2},
            {'text': '第三段', 'scene_id': 3},
        ]
        
        tts = SegmentedTTS()
        results = await tts.synthesize_segments(segments, './test_tts')
        
        for r in results:
            print(f"  场景{r['scene_id']}: {r['duration']:.1f}秒 - {r['audio_path']}")
    
    asyncio.run(test())

