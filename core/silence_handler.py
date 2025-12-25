# core/silence_handler.py - 静音处理器 v5.6
"""
SmartVideoClipper - 静音处理器 v5.6

核心功能：
1. 检测解说场景中的静音段落
2. 通过AI扩展解说填充静音（优先）
3. 计算建议TTS语速调整

设计原则：
- 静音检测：TTS预估时长 < 场景时长 * 0.7
- 优先扩展解说内容
- 语速调整作为辅助手段
"""

import sys
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def log(msg: str):
    """统一日志输出"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


@dataclass
class SilenceGap:
    """静音段落信息"""
    scene_id: int           # 场景ID
    scene_duration: float   # 场景时长(秒)
    tts_duration: float     # TTS预估时长(秒)
    gap_duration: float     # 静音时长(秒)
    need_chars: int         # 需要补充的字数
    current_narration: str  # 当前解说
    expanded_narration: str = ""  # 扩展后解说
    suggested_rate: float = 1.0   # 建议语速


class SilenceHandler:
    """
    静音处理器 v5.6
    
    职责：
    1. 检测静音段落
    2. AI扩展解说填充
    3. 计算语速调整
    """
    
    # 语速：每秒4个汉字
    SPEECH_RATE = 4.0
    
    # 静音阈值：TTS时长 < 场景时长 * 0.7
    SILENCE_THRESHOLD = 0.7
    
    # 语速调整范围
    MIN_SPEED = 0.85
    MAX_SPEED = 1.15
    
    def __init__(self, llm_model: str = None):
        """
        初始化静音处理器
        
        参数：
            llm_model: Ollama模型名称
        """
        self.llm_model = llm_model
        if not llm_model:
            self._init_llm()
    
    def _init_llm(self):
        """初始化LLM模型"""
        try:
            import ollama
            models = ollama.list()
            
            available = []
            for model in models.get('models', []):
                name = model.get('name', '') or model.get('model', '')
                if name:
                    available.append(name)
            
            # v5.7.3: qwen3的content字段有正确输出
            priority = ['qwen3', 'qwen2.5', 'qwen', 'llama3', 'gemma', 'mistral']
            for p in priority:
                for a in available:
                    if p in a.lower():
                        self.llm_model = a
                        return
            
            if available:
                self.llm_model = available[0]
        except Exception:
            self.llm_model = None
    
    def _detect_silence_type(
        self,
        dialogue: str,
        emotion: str,
        prev_scene: Dict = None,
        next_scene: Dict = None
    ) -> Tuple[str, str]:
        """
        v5.7：检测静音类型并返回扩展策略
        
        静音类型：
        - emotion_brewing: 情绪酝酿（强情感前后）
        - environment_transition: 环境过渡
        - before_climax: 高潮前夕
        - action_scene: 动作场景
        - flashback: 回忆/闪回
        - confrontation: 对峙场景
        - default: 默认
        """
        # 检测情绪酝酿
        strong_emotions = ['angry', 'sad', 'crying', 'excited']
        if emotion in strong_emotions:
            return "情绪酝酿", "描述角色此刻的内心挣扎、情感波动，让观众感受人物的心理活动"
        
        # 检测是否在高潮前夕
        if next_scene:
            next_importance = next_scene.get('importance', 0)
            next_emotion = next_scene.get('emotion', '')
            if next_importance >= 0.8 or next_emotion in strong_emotions:
                return "高潮前夕", "铺垫即将到来的转折，用'谁也没想到''命运的齿轮'等方式营造悬念"
        
        # 检测环境过渡
        if not dialogue or len(dialogue) < 10:
            if prev_scene and next_scene:
                return "环境过渡", "描述场景变换、时间流逝，如'夜幕降临''几个小时后'等自然衔接"
        
        # 检测对峙场景
        if dialogue and ('你' in dialogue or '我' in dialogue) and emotion in ['angry', 'neutral']:
            return "对峙场景", "分析双方的态势和心理，描述紧张的气氛"
        
        # 检测动作场景（无对话但重要）
        if not dialogue and prev_scene and prev_scene.get('importance', 0) > 0.6:
            return "动作场景", "描述动作的意义和影响，解释画面中发生了什么"
        
        # 默认策略
        return "剧情推进", "补充背景信息、人物关系或与整体故事的联系"
    
    def detect_silence_gaps(self, scenes: List[Dict]) -> List[SilenceGap]:
        """
        检测静音段落
        
        参数：
            scenes: 场景列表，需要包含：
                - scene_id: 场景ID
                - start_time: 开始时间
                - end_time: 结束时间
                - audio_mode: 音频模式 (voiceover才检测)
                - narration: 解说文本
        
        返回：静音段落列表
        """
        gaps = []
        
        for scene in scenes:
            # 只检测解说场景
            if scene.get('audio_mode') != 'voiceover':
                continue
            
            narration = scene.get('narration', '')
            if not narration:
                continue
            
            scene_duration = scene.get('end_time', 0) - scene.get('start_time', 0)
            if scene_duration <= 0:
                continue
            
            # 计算TTS预估时长
            tts_duration = len(narration) / self.SPEECH_RATE
            
            # 检测静音
            if tts_duration < scene_duration * self.SILENCE_THRESHOLD:
                gap_duration = scene_duration - tts_duration
                need_chars = int(gap_duration * self.SPEECH_RATE)
                
                gap = SilenceGap(
                    scene_id=scene.get('scene_id', 0),
                    scene_duration=scene_duration,
                    tts_duration=tts_duration,
                    gap_duration=gap_duration,
                    need_chars=need_chars,
                    current_narration=narration
                )
                gaps.append(gap)
        
        return gaps
    
    def process_silence_gaps(
        self,
        gaps: List[SilenceGap],
        scenes: List[Dict],
        plot_summary: str = "",
        style: str = "幽默"
    ) -> Tuple[List[SilenceGap], int, int]:
        """
        处理静音段落
        
        参数：
            gaps: 静音段落列表
            scenes: 完整场景列表（用于获取上下文）
            plot_summary: 剧情概要
            style: 解说风格
        
        返回：(处理后的gaps, 成功扩展数, 语速调整数)
        """
        if not gaps:
            return gaps, 0, 0
        
        log(f"[Silence] ========== 静音处理 v5.6 ==========")
        log(f"[Silence] 检测到静音段落: {len(gaps)}个")
        
        expanded_count = 0
        rate_adjusted_count = 0
        
        # 构建场景索引
        scene_map = {s.get('scene_id', i): s for i, s in enumerate(scenes)}
        
        for gap in gaps:
            # 获取场景上下文
            scene = scene_map.get(gap.scene_id, {})
            dialogue = scene.get('dialogue', '')
            emotion = scene.get('emotion', 'neutral')
            
            # 尝试AI扩展
            if self.llm_model:
                expanded = self._expand_narration(
                    gap.current_narration,
                    gap.need_chars,
                    dialogue,
                    emotion,
                    plot_summary,
                    style
                )
                
                if expanded and len(expanded) > len(gap.current_narration):
                    gap.expanded_narration = expanded
                    expanded_count += 1
                    
                    # 重新计算是否还需要语速调整
                    new_tts_duration = len(expanded) / self.SPEECH_RATE
                    if new_tts_duration < gap.scene_duration * 0.85:
                        # 还有轻微静音，微调语速
                        gap.suggested_rate = self._calculate_speech_rate(
                            len(expanded), gap.scene_duration, emotion
                        )
                        if gap.suggested_rate != 1.0:
                            rate_adjusted_count += 1
                    continue
            
            # AI扩展失败，使用语速调整
            gap.expanded_narration = gap.current_narration
            gap.suggested_rate = self._calculate_speech_rate(
                len(gap.current_narration), gap.scene_duration, emotion
            )
            if gap.suggested_rate != 1.0:
                rate_adjusted_count += 1
        
        log(f"[Silence] AI扩展成功: {expanded_count}个")
        log(f"[Silence] 语速调整: {rate_adjusted_count}个")
        log(f"[Silence] ========== 处理完成 ==========")
        
        return gaps, expanded_count, rate_adjusted_count
    
    def _expand_narration(
        self,
        narration: str,
        need_chars: int,
        dialogue: str,
        emotion: str,
        plot_summary: str,
        style: str,
        prev_scene: Dict = None,
        next_scene: Dict = None
    ) -> Optional[str]:
        """
        v5.7改进：AI扩展解说，根据静音类型选择策略
        
        参数：
            narration: 当前解说
            need_chars: 需要补充的字数
            dialogue: 场景对话
            emotion: 情感
            plot_summary: 剧情概要
            style: 风格
            prev_scene: 前一场景（用于上下文）
            next_scene: 后一场景（用于上下文）
        
        返回：扩展后的解说
        """
        if not self.llm_model:
            return None
        
        try:
            import ollama
            
            target_chars = len(narration) + need_chars
            
            # v5.7：检测静音类型，选择扩展策略
            silence_type, strategy = self._detect_silence_type(
                dialogue, emotion, prev_scene, next_scene
            )
            
            # 构建上下文
            prev_context = ""
            next_context = ""
            if prev_scene:
                prev_dialogue = prev_scene.get('dialogue', '')[:50]
                prev_context = f"- 前一场景：{prev_dialogue if prev_dialogue else '(无对话)'}"
            if next_scene:
                next_dialogue = next_scene.get('dialogue', '')[:50]
                next_context = f"- 后一场景：{next_dialogue if next_dialogue else '(无对话)'}"
            
            # v5.7.2: 简化prompt，禁止思考
            prompt = f"""/no_think
扩展解说到{target_chars}字：

原文：{narration}
场景：{dialogue[:60] if dialogue else '(无)'}
风格：{style}

规则：直接输出扩展后的解说，禁止输出"好的"、"首先"等思考过程。

输出："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 500,
                    'temperature': 0.5,
                }
            )
            
            # v5.7.3: 只从content提取，绝不使用thinking
            msg = response.get('message', {})
            result = ""
            
            if hasattr(msg, 'content') and msg.content:
                result = msg.content.strip()
            
            # v5.7.3: content为空返回None
            if not result:
                return None
            
            # 清理格式
            result = result.strip('"\'')
            
            # 验证长度
            if len(result) < len(narration):
                return None
            
            return result
            
        except Exception as e:
            log(f"[Silence] AI扩展异常: {e}")
            return None
    
    def _calculate_speech_rate(
        self,
        char_count: int,
        scene_duration: float,
        emotion: str
    ) -> float:
        """
        计算建议语速
        
        参数：
            char_count: 解说字数
            scene_duration: 场景时长
            emotion: 情感
        
        返回：建议语速 (0.85 ~ 1.15)
        """
        if scene_duration <= 0 or char_count <= 0:
            return 1.0
        
        # 计算需要的语速
        required_rate = char_count / scene_duration
        speed_ratio = required_rate / self.SPEECH_RATE
        
        # 情感调整
        if emotion == 'sad':
            speed_ratio *= 0.95  # 悲伤放慢
        elif emotion == 'angry':
            speed_ratio *= 1.05  # 愤怒加速
        elif emotion == 'excited':
            speed_ratio *= 1.03  # 兴奋微加速
        
        # 限制范围
        speed_ratio = max(self.MIN_SPEED, min(self.MAX_SPEED, speed_ratio))
        
        # 微小调整不生效（避免过度调整）
        if 0.95 <= speed_ratio <= 1.05:
            return 1.0
        
        return round(speed_ratio, 2)
    
    def apply_to_scenes(
        self,
        scenes: List[Dict],
        gaps: List[SilenceGap]
    ) -> List[Dict]:
        """
        将处理结果应用到场景列表
        
        参数：
            scenes: 原场景列表
            gaps: 处理后的静音段落
        
        返回：更新后的场景列表
        """
        # 构建gap映射
        gap_map = {g.scene_id: g for g in gaps}
        
        for scene in scenes:
            scene_id = scene.get('scene_id', 0)
            if scene_id in gap_map:
                gap = gap_map[scene_id]
                
                # 更新解说
                if gap.expanded_narration:
                    scene['narration'] = gap.expanded_narration
                
                # 添加语速建议
                if gap.suggested_rate != 1.0:
                    scene['speech_rate'] = gap.suggested_rate
        
        return scenes
    
    def get_statistics(self, gaps: List[SilenceGap]) -> Dict:
        """获取统计信息"""
        if not gaps:
            return {
                'total_gaps': 0,
                'total_silence_duration': 0,
                'expanded_count': 0,
                'rate_adjusted_count': 0,
            }
        
        total_silence = sum(g.gap_duration for g in gaps)
        expanded = sum(1 for g in gaps if g.expanded_narration and g.expanded_narration != g.current_narration)
        rate_adjusted = sum(1 for g in gaps if g.suggested_rate != 1.0)
        
        return {
            'total_gaps': len(gaps),
            'total_silence_duration': total_silence,
            'expanded_count': expanded,
            'rate_adjusted_count': rate_adjusted,
            'avg_gap_duration': total_silence / len(gaps),
        }


def estimate_tts_duration(text: str, speech_rate: float = 4.0) -> float:
    """
    估算TTS时长
    
    参数：
        text: 解说文本
        speech_rate: 语速（字/秒）
    
    返回：预估时长（秒）
    """
    if not text:
        return 0.0
    return len(text) / speech_rate


# 测试
if __name__ == "__main__":
    handler = SilenceHandler()
    
    # 测试场景
    test_scenes = [
        {
            'scene_id': 1,
            'start_time': 0,
            'end_time': 10,
            'audio_mode': 'voiceover',
            'narration': '短解说',  # 2字，0.5秒，场景10秒 → 静音
            'dialogue': '这是一段很长的对话内容',
            'emotion': 'neutral',
        },
        {
            'scene_id': 2,
            'start_time': 10,
            'end_time': 15,
            'audio_mode': 'voiceover',
            'narration': '这是一段正常长度的解说文本',  # 13字，3.25秒，场景5秒 → 正常
            'dialogue': '',
            'emotion': 'sad',
        },
        {
            'scene_id': 3,
            'start_time': 15,
            'end_time': 30,
            'audio_mode': 'voiceover',
            'narration': '又一段短解说',  # 6字，1.5秒，场景15秒 → 静音
            'dialogue': '对话内容',
            'emotion': 'angry',
        },
    ]
    
    # 检测静音
    gaps = handler.detect_silence_gaps(test_scenes)
    print(f"\n检测到静音: {len(gaps)}个")
    for gap in gaps:
        print(f"  场景{gap.scene_id}: 时长{gap.scene_duration}s, TTS{gap.tts_duration:.1f}s, "
              f"静音{gap.gap_duration:.1f}s, 需补{gap.need_chars}字")
    
    # 处理静音
    gaps, expanded, adjusted = handler.process_silence_gaps(gaps, test_scenes, "测试剧情")
    
    print(f"\n处理结果:")
    print(f"  扩展成功: {expanded}")
    print(f"  语速调整: {adjusted}")
    
    for gap in gaps:
        print(f"\n  场景{gap.scene_id}:")
        print(f"    原解说: {gap.current_narration}")
        print(f"    新解说: {gap.expanded_narration}")
        print(f"    建议语速: {gap.suggested_rate}x")

