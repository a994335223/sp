# core/tts_segmented.py - 分段TTS合成器 v5.6
"""
SmartVideoClipper - 分段语音合成 v5.6 (动态语速版)

核心原则：
每个解说场景单独生成一个音频文件！

v5.6 核心改进：
1. 动态语速控制：支持0.85x-1.15x语速调整
2. 情感语速适配：悲伤放慢、愤怒加速
3. 静音填充配合：根据scene的speech_rate调整

v5.3 基础保留：
1. 修复语音卡顿问题（优化文本预处理）
2. 简化音频后处理（减少过度处理）
3. 更短的淡入淡出（0.03秒）
4. 更好的错误恢复机制
"""

import os
import re
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 尝试加载配置
try:
    from config import TTS_VOICE, TTS_RATE, TTS_FADE_DURATION
except ImportError:
    TTS_VOICE = "zh-CN-YunxiNeural"
    TTS_RATE = "-5%"
    TTS_FADE_DURATION = 0.03


class SegmentedTTS:
    """
    分段TTS合成器 v5.6
    
    每个解说场景生成独立的音频文件
    支持动态语速控制
    """
    
    # v5.6: 动态语速范围
    MIN_SPEED = 0.85
    MAX_SPEED = 1.15
    
    def __init__(self, voice: str = None):
        """
        初始化
        
        voice: Edge-TTS 语音
            - zh-CN-YunxiNeural (男声，推荐)
            - zh-CN-XiaoxiaoNeural (女声)
            - zh-CN-YunyangNeural (男声，新闻风格)
        """
        self.voice = voice or TTS_VOICE
        self.rate = TTS_RATE
        self.fade_duration = TTS_FADE_DURATION
        
        print(f"[TTS] 分段合成器 v5.6 初始化 (动态语速版)")
        print(f"      语音: {self.voice}")
        print(f"      基础语速: {self.rate}")
        print(f"      动态语速范围: {self.MIN_SPEED}x - {self.MAX_SPEED}x")
    
    def _optimize_text_for_tts(self, text: str) -> str:
        """
        优化文本，减少TTS卡顿 v5.3
        
        核心改进：
        1. 保持语句流畅自然
        2. 减少不必要的停顿标点
        3. 确保句子完整
        """
        if not text:
            return ""
        
        # ===== 第一步：移除垃圾内容 =====
        bad_phrases = [
            '情节推进中', '故事继续发展', '剧情推进', '故事推进',
            '接下来', '紧接着', '然后呢',
            '精彩画面', '精彩片段', '重要场景',
            '解说文本', '解说词', '旁白',
        ]
        for phrase in bad_phrases:
            text = text.replace(phrase, '')
        
        # ===== 第二步：清理格式 =====
        # 中文不需要空格
        text = re.sub(r'\s+', '', text.strip())
        
        # 关键改进：省略号会导致长停顿，替换为短顿号
        text = text.replace('...', '、')
        text = text.replace('…', '、')
        text = text.replace('——', '、')
        text = text.replace('--', '、')
        
        # 统一逗号类型
        text = text.replace(',', '，')
        text = text.replace(';', '；')
        
        # 移除连续标点（保留最后一个）
        text = re.sub(r'[，、]{2,}', '，', text)
        text = re.sub(r'[。！？]{2,}', '。', text)
        
        # 移除括号（但保留内容）
        text = re.sub(r'[（\(]', '', text)
        text = re.sub(r'[）\)]', '', text)
        text = re.sub(r'[\[【]', '', text)
        text = re.sub(r'[\]】]', '', text)
        
        # ===== 第三步：确保句子完整流畅 =====
        text = text.strip()
        
        if not text:
            return ""
        
        # 移除开头的标点
        text = text.lstrip('，。！？、；')
        
        # 句子太短则返回空
        if len(text) < 4:
            return ""
        
        # 确保以句号结尾（句号比逗号更自然）
        if text[-1] not in '。！？':
            text = text.rstrip('，、；') + '。'
        
        return text
    
    async def synthesize_segments(
        self,
        segments: List[Dict],
        output_dir: str,
        target_durations: List[float] = None
    ) -> List[Dict]:
        """
        为每个解说段落生成音频 v5.6（支持动态语速）
        
        参数：
            segments: 解说段落列表，每项包含：
                - text: 解说文本
                - scene_id: 场景ID
                - speech_rate: (可选) 动态语速 0.85-1.15
                - emotion: (可选) 情感，用于语速调整
            target_durations: 目标时长列表
        """
        import time
        from datetime import datetime
        
        def log(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
        
        os.makedirs(output_dir, exist_ok=True)
        
        start_time = time.time()
        log(f"[TTS] ========== TTS语音合成开始 v5.6 ==========")
        log(f"[TTS] 待合成片段: {len(segments)} 个")
        log(f"[TTS] 输出目录: {output_dir}")
        log(f"[TTS] 语音: {self.voice}")
        
        # v5.6: 统计动态语速使用情况
        dynamic_rate_count = sum(1 for s in segments if s.get('speech_rate', 1.0) != 1.0)
        if dynamic_rate_count > 0:
            log(f"[TTS] 动态语速片段: {dynamic_rate_count} 个")
        
        results = []
        success_count = 0
        fail_count = 0
        
        for i, seg in enumerate(segments):
            text = seg.get('text', '').strip()
            scene_id = seg.get('scene_id', i + 1)
            
            if not text:
                continue
            
            audio_path = os.path.join(output_dir, f"narration_{scene_id:04d}.wav")
            
            # 目标时长
            target_duration = None
            if target_durations and i < len(target_durations):
                target_duration = target_durations[i]
            
            # v5.6: 获取动态语速
            speech_rate = seg.get('speech_rate', 1.0)
            emotion = seg.get('emotion', 'neutral')
            
            # 合成音频（传入动态语速参数）
            success, duration = await self._synthesize_single(
                text, audio_path, target_duration,
                speech_rate=speech_rate, emotion=emotion
            )
            
            if success:
                results.append({
                    'audio_path': audio_path,
                    'duration': duration,
                    'scene_id': scene_id,
                    'text': text,
                    'start': 0,
                    'speech_rate': speech_rate,  # v5.6: 记录使用的语速
                })
                success_count += 1
            else:
                fail_count += 1
            
            # 每5个或最后一个显示进度
            if (i + 1) % 5 == 0 or i == len(segments) - 1:
                elapsed = time.time() - start_time
                progress = (i + 1) / len(segments) * 100
                log(f"[TTS] 进度: {i+1}/{len(segments)} ({progress:.0f}%) | 成功:{success_count} 失败:{fail_count} | 耗时:{elapsed:.0f}秒")
        
        total_duration = sum(r['duration'] for r in results)
        total_time = time.time() - start_time
        log(f"[TTS] ========== TTS语音合成完成 ==========")
        log(f"[TTS] 成功: {success_count} | 失败: {fail_count}")
        log(f"[TTS] 总音频时长: {total_duration:.1f}秒")
        log(f"[TTS] 合成耗时: {total_time:.1f}秒")
        
        return results
    
    async def _synthesize_single(
        self,
        text: str,
        output_path: str,
        target_duration: float = None,
        max_retries: int = 3,
        speech_rate: float = 1.0,
        emotion: str = 'neutral'
    ) -> Tuple[bool, float]:
        """
        合成单个音频 v5.6
        
        v5.6改进：
        - 支持动态语速 (0.85-1.15)
        - 情感语速适配
        
        参数：
            speech_rate: 动态语速，默认1.0
            emotion: 情感，用于微调语速
        """
        try:
            import edge_tts
            
            # 优化文本
            optimized_text = self._optimize_text_for_tts(text)
            if not optimized_text:
                return False, 0
            
            temp_mp3 = output_path + '.temp.mp3'
            
            # v5.6: 计算Edge-TTS的rate参数
            # Edge-TTS rate格式: "+10%", "-5%" 等
            # 基础rate是-5%，需要根据speech_rate调整
            tts_rate = self._calculate_tts_rate(speech_rate, emotion)
            
            # 重试机制
            success = False
            for attempt in range(max_retries):
                try:
                    communicate = edge_tts.Communicate(
                        optimized_text, 
                        self.voice, 
                        rate=tts_rate  # v5.6: 使用动态计算的rate
                    )
                    await communicate.save(temp_mp3)
                    
                    if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 100:
                        success = True
                        break
                        
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"   [RETRY] TTS第{attempt+1}次失败，重试...")
                        await asyncio.sleep(0.5)
                    else:
                        print(f"   [ERROR] TTS合成失败: {e}")
            
            if not success or not os.path.exists(temp_mp3):
                return False, 0
            
            # ===== 简化后处理 v5.3 =====
            # 直接转换为WAV（不做额外处理）
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_mp3,
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                '-loglevel', 'error',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            
            # 清理临时文件
            try:
                os.remove(temp_mp3)
            except:
                pass
            
            if not os.path.exists(output_path):
                return False, 0
            
            # 获取时长
            duration = self._get_audio_duration(output_path)
            
            # 只对长音频(>3秒)添加淡入淡出
            if duration > 3.0 and self.fade_duration > 0:
                self._add_fade(output_path, duration)
                duration = self._get_audio_duration(output_path)  # 重新获取
            
            # v5.6: 只在动态语速无法完全填充时才后处理调速
            if target_duration and duration > 0 and speech_rate == 1.0:
                speed_ratio = duration / target_duration
                # 只在差异很大时才调速
                if speed_ratio > 1.6:
                    self._adjust_speed(output_path, min(speed_ratio, 1.8))
                    duration = self._get_audio_duration(output_path)
            
            return True, duration
            
        except Exception as e:
            print(f"   [ERROR] TTS合成异常: {e}")
            return False, 0
    
    def _calculate_tts_rate(self, speech_rate: float, emotion: str) -> str:
        """
        v5.6新增：计算Edge-TTS的rate参数
        
        Edge-TTS rate格式: "+10%", "-5%" 等
        基础rate是-5%，需要根据speech_rate调整
        
        参数：
            speech_rate: 动态语速 (0.85-1.15)
            emotion: 情感
        
        返回：Edge-TTS rate字符串
        """
        # 基础rate对应的百分比
        # self.rate = "-5%" 对应正常语速
        base_percent = -5
        
        # speech_rate转换为百分比调整
        # 1.0 = 0% 调整
        # 0.85 = -15% 调整 (放慢)
        # 1.15 = +15% 调整 (加速)
        rate_adjustment = (speech_rate - 1.0) * 100
        
        # 情感微调
        emotion_adjustment = 0
        if emotion == 'sad':
            emotion_adjustment = -5  # 悲伤再放慢5%
        elif emotion == 'angry':
            emotion_adjustment = +3  # 愤怒加速3%
        elif emotion == 'excited':
            emotion_adjustment = +2  # 兴奋加速2%
        
        # 计算最终rate
        final_percent = base_percent + rate_adjustment + emotion_adjustment
        
        # 限制范围 (-30% ~ +20%)
        final_percent = max(-30, min(20, final_percent))
        
        # 转换为字符串格式
        if final_percent >= 0:
            return f"+{int(final_percent)}%"
        else:
            return f"{int(final_percent)}%"
    
    def _add_fade(self, audio_path: str, duration: float):
        """添加淡入淡出（简化版）"""
        fade_in = self.fade_duration
        fade_out = self.fade_duration
        fade_out_start = max(0, duration - fade_out)
        
        faded_path = audio_path + '.faded.wav'
        cmd = [
            'ffmpeg', '-y',
            '-i', audio_path,
            '-af', f'afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}',
            '-acodec', 'pcm_s16le',
            '-loglevel', 'error',
            faded_path
        ]
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if os.path.exists(faded_path) and os.path.getsize(faded_path) > 100:
            os.replace(faded_path, audio_path)
    
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
    
    def _adjust_speed(self, audio_path: str, speed_ratio: float):
        """调整音频速度（保守调整）"""
        # 限制调速范围
        speed_ratio = max(0.8, min(1.8, speed_ratio))
        
        adjusted_path = audio_path + '.adjusted.wav'
        cmd = [
            'ffmpeg', '-y',
            '-i', audio_path,
            '-filter:a', f'atempo={speed_ratio}',
            '-acodec', 'pcm_s16le',
            '-loglevel', 'error',
            adjusted_path
        ]
        subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        if os.path.exists(adjusted_path) and os.path.getsize(adjusted_path) > 100:
            os.replace(adjusted_path, audio_path)


async def synthesize_timeline_narrations(
    timeline: List[Dict],
    output_dir: str,
    voice: str = None
) -> List[Dict]:
    """
    为时间线中的解说场景生成音频 v5.6
    
    参数：
        timeline: 时间线，每项需要 audio_mode 和 narration 字段
                  v5.6新增：speech_rate（动态语速）、emotion（情感）
        output_dir: 输出目录
        voice: TTS语音
    
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
                segment = {
                    'text': narration,
                    'scene_id': item.get('scene_id', len(voiceover_segments) + 1),
                    # v5.6: 传递动态语速和情感
                    'speech_rate': item.get('speech_rate', 1.0),
                    'emotion': item.get('emotion', 'neutral'),
                }
                voiceover_segments.append(segment)
                
                # 目标时长 = 场景时长
                duration = item.get('source_end', 0) - item.get('source_start', 0)
                target_durations.append(duration)
    
    if not voiceover_segments:
        print("[TTS] 没有需要合成的解说段落")
        return []
    
    # v5.6: 统计动态语速使用
    dynamic_count = sum(1 for s in voiceover_segments if s.get('speech_rate', 1.0) != 1.0)
    if dynamic_count > 0:
        print(f"[TTS] 动态语速场景: {dynamic_count}个")
    
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
            {'text': '这是第一段解说内容，故事正在展开', 'scene_id': 1},
            {'text': '事态有了新的发展，所有人都很紧张', 'scene_id': 2},
            {'text': '关键时刻到来了', 'scene_id': 3},
        ]
        
        tts = SegmentedTTS()
        results = await tts.synthesize_segments(segments, './test_tts_v53')
        
        for r in results:
            print(f"  场景{r['scene_id']}: {r['duration']:.1f}秒 - {r['audio_path']}")
    
    asyncio.run(test())
