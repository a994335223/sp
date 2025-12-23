# core/tts_segmented.py - 分段TTS合成器 v5.3
"""
SmartVideoClipper - 分段语音合成 v5.3 (全球最优版)

核心原则：
每个解说场景单独生成一个音频文件！

v5.3 核心改进：
1. 修复语音卡顿问题（优化文本预处理）
2. 简化音频后处理（减少过度处理）
3. 更稳定的语速控制
4. 更短的淡入淡出（0.03秒）
5. 更好的错误恢复机制
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
    分段TTS合成器 v5.3
    
    每个解说场景生成独立的音频文件
    优化文本处理，减少卡顿
    """
    
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
        
        print(f"[TTS] 分段合成器 v5.3 初始化")
        print(f"      语音: {self.voice}")
        print(f"      语速: {self.rate}")
        print(f"      淡入淡出: {self.fade_duration}秒")
    
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
        为每个解说段落生成音频（带详细日志）
        """
        import time
        from datetime import datetime
        
        def log(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
        
        os.makedirs(output_dir, exist_ok=True)
        
        start_time = time.time()
        log(f"[TTS] ========== TTS语音合成开始 ==========")
        log(f"[TTS] 待合成片段: {len(segments)} 个")
        log(f"[TTS] 输出目录: {output_dir}")
        log(f"[TTS] 语音: {self.voice}")
        
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
                    'start': 0,
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
        max_retries: int = 3
    ) -> Tuple[bool, float]:
        """
        合成单个音频 v5.3
        
        改进：简化后处理流程，减少过度处理
        """
        try:
            import edge_tts
            
            # 优化文本
            optimized_text = self._optimize_text_for_tts(text)
            if not optimized_text:
                return False, 0
            
            temp_mp3 = output_path + '.temp.mp3'
            
            # 重试机制
            success = False
            for attempt in range(max_retries):
                try:
                    communicate = edge_tts.Communicate(
                        optimized_text, 
                        self.voice, 
                        rate=self.rate
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
            
            # 调速（更保守）
            if target_duration and duration > 0:
                speed_ratio = duration / target_duration
                # 只在差异很大时才调速（原1.3改为1.6）
                if speed_ratio > 1.6:
                    self._adjust_speed(output_path, min(speed_ratio, 1.8))
                    duration = self._get_audio_duration(output_path)
            
            return True, duration
            
        except Exception as e:
            print(f"   [ERROR] TTS合成异常: {e}")
            return False, 0
    
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
    为时间线中的解说场景生成音频
    
    参数：
        timeline: 时间线，每项需要 audio_mode 和 narration 字段
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
            {'text': '这是第一段解说内容，故事正在展开', 'scene_id': 1},
            {'text': '事态有了新的发展，所有人都很紧张', 'scene_id': 2},
            {'text': '关键时刻到来了', 'scene_id': 3},
        ]
        
        tts = SegmentedTTS()
        results = await tts.synthesize_segments(segments, './test_tts_v53')
        
        for r in results:
            print(f"  场景{r['scene_id']}: {r['duration']:.1f}秒 - {r['audio_path']}")
    
    asyncio.run(test())
