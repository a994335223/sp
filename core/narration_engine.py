# core/narration_engine.py - 解说引擎 v5.1 (电影/电视剧分离版)
"""
SmartVideoClipper - 智能解说引擎 v5.1

🎬 核心升级：电影与电视剧模式分离

电视剧模式（TV）：
- 需要指定第几集
- 解说聚焦"当前集"剧情，不是整部剧
- 解说比例更高（60%），让观众快速了解本集内容
- 适合"3分钟看完一集"的解说风格

电影模式（Movie）：
- 可指定系列电影第几部
- 解说涵盖整体剧情脉络
- 原声比例更高（60%），保留经典台词
- 适合"精彩片段集锦"风格

三种音频模式：
- 🔊 原声场景：精彩对话、情感爆发、动作高潮
- 🎙️ 解说场景：过渡、背景交代、快进
- 🔇 跳过场景：无意义、重复、拖沓
"""

import os
import sys
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# 敏感词列表
SENSITIVE_WORDS = [
    "习近平", "胡锦涛", "江泽民", "毛泽东", "邓小平", "温家宝", "李克强",
    "习主席", "总书记", "国家主席", "中央领导", "共产党", "国民党", 
    "民进党", "法轮功", "六四", "天安门", "台独", "藏独", "疆独", "港独",
]

# 低质量内容检测
BAD_PATTERNS = [
    "紧张的场面", "紧张的一幕", "此刻紧张", "画面一转，紧张",
    "未知场景", "unknown", "场景1", "场景2",
]


class AudioMode(Enum):
    ORIGINAL = "original"    # 保留原声
    VOICEOVER = "voiceover"  # 使用解说
    SKIP = "skip"            # 跳过


@dataclass
class SceneSegment:
    """场景片段"""
    scene_id: int
    start_time: float
    end_time: float
    dialogue: str           # 原始对话
    narration: str          # 生成的解说（如果需要）
    audio_mode: AudioMode   # 音频模式
    importance: float       # 重要性分数
    emotion: str            # 情感
    reason: str             # 选择原因（调试用）
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class NarrationEngine:
    """
    智能解说引擎 v5.1
    
    核心职责：
    1. 根据媒体类型（电影/电视剧）选择不同策略
    2. 分析场景，决定原声/解说/跳过
    3. 为解说场景生成高质量文案
    4. 确保剧情连贯性
    """
    
    def __init__(self, use_ai: bool = True, media_type: str = "tv", episode: int = 1):
        """
        初始化解说引擎
        
        参数：
            use_ai: 是否使用AI生成
            media_type: 媒体类型 ("tv" 电视剧, "movie" 电影)
            episode: 集数/部数 (电视剧第几集 或 电影第几部)
        """
        self.use_ai = use_ai
        self.llm_model = None
        self.media_type = media_type
        self.episode = episode
        
        # 根据媒体类型设置策略
        if media_type == "tv":
            # 电视剧：更多解说，讲当前集的故事
            self.voiceover_ratio = 0.6  # 60%解说
            self.min_original_ratio = 0.25  # 最少25%原声
        else:
            # 电影：更多原声，保留经典台词
            self.voiceover_ratio = 0.4  # 40%解说
            self.min_original_ratio = 0.45  # 最少45%原声
        
        # 尝试加载LLM
        if use_ai:
            self._init_llm()
    
    def _init_llm(self):
        """初始化LLM模型"""
        try:
            import ollama
            models = ollama.list()
            
            # 获取可用模型
            available = []
            for model in models.get('models', []):
                name = model.get('name', '') or model.get('model', '')
                if name:
                    available.append(name.split(':')[0])
            
            # 优先级选择
            priority = ['qwen3', 'qwen2.5', 'qwen', 'llama3', 'gemma']
            for p in priority:
                for a in available:
                    if p in a.lower():
                        self.llm_model = a
                        print(f"[LLM] 使用模型: {self.llm_model}")
                        return
            
            if available:
                self.llm_model = available[0]
                print(f"[LLM] 使用模型: {self.llm_model}")
        except Exception as e:
            print(f"[LLM] 初始化失败: {e}")
            self.llm_model = None
    
    def analyze_and_generate(
        self,
        scenes: List[Dict],
        title: str = "",
        style: str = "幽默",
        episode_plot: str = ""
    ) -> Tuple[List[SceneSegment], str]:
        """
        分析场景并生成解说
        
        参数：
            scenes: 场景列表
            title: 作品名称
            style: 解说风格
            episode_plot: 分集剧情（电视剧用）
        
        返回：(处理后的场景列表, 完整解说文本)
        """
        print("\n" + "="*60)
        print("[Engine] 智能解说引擎 v5.1")
        print("="*60)
        print(f"   作品: {title}")
        print(f"   类型: {'电视剧' if self.media_type == 'tv' else '电影'}")
        if self.media_type == "tv":
            print(f"   集数: 第{self.episode}集")
        else:
            print(f"   部数: 第{self.episode}部")
        print(f"   风格: {style}")
        print(f"   场景数: {len(scenes)}")
        print(f"   解说比例目标: {self.voiceover_ratio*100:.0f}%")
        print("="*60)
        
        # 保存分集剧情供后续使用
        self.episode_plot = episode_plot
        
        # Step 1: 理解整体剧情
        print("\n[Step 1] 理解剧情脉络...")
        plot_summary = self._understand_plot(scenes)
        print(f"   剧情概要: {plot_summary[:100]}...")
        
        # Step 2: 标记场景类型
        print("\n[Step 2] 分析场景类型...")
        marked_scenes = self._mark_scenes(scenes)
        
        # Step 3: 生成解说
        print("\n[Step 3] 生成解说文案...")
        final_scenes = self._generate_narrations(marked_scenes, plot_summary, style)
        
        # Step 4: 优化连贯性
        print("\n[Step 4] 优化剧情连贯性...")
        final_scenes = self._optimize_continuity(final_scenes)
        
        # 统计
        original_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.ORIGINAL)
        voiceover_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.VOICEOVER)
        skip_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.SKIP)
        
        total_duration = sum(s.duration for s in final_scenes if s.audio_mode != AudioMode.SKIP)
        
        print("\n" + "="*60)
        print("📊 分析结果:")
        print(f"   🔊 原声场景: {original_count} ({original_count*100//(original_count+voiceover_count+1)}%)")
        print(f"   🎙️ 解说场景: {voiceover_count} ({voiceover_count*100//(original_count+voiceover_count+1)}%)")
        print(f"   🔇 跳过场景: {skip_count}")
        print(f"   ⏱️ 预计时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        print("="*60)
        
        # 生成完整解说文本（只包含解说场景）
        full_narration = self._compile_narration_text(final_scenes)
        
        return final_scenes, full_narration
    
    def _understand_plot(self, scenes: List[Dict]) -> str:
        """理解整体剧情"""
        # 收集所有对话
        all_dialogues = []
        for scene in scenes:
            dialogue = scene.get('dialogue', '').strip()
            if dialogue and len(dialogue) > 10:
                # 过滤敏感词
                dialogue = self._filter_sensitive(dialogue)
                if dialogue:
                    all_dialogues.append(dialogue)
        
        if not all_dialogues:
            return "无法识别剧情内容"
        
        # 用AI总结（如果可用）
        if self.llm_model:
            combined = "\n".join(all_dialogues[:50])  # 取前50段
            summary = self._ai_summarize(combined)
            if summary:
                return summary
        
        # 备用：简单拼接
        return " ".join(all_dialogues[:10])[:500]
    
    def _mark_scenes(self, scenes: List[Dict]) -> List[SceneSegment]:
        """标记每个场景的类型"""
        result = []
        
        for i, scene in enumerate(scenes):
            dialogue = scene.get('dialogue', '').strip()
            emotion = scene.get('emotion', 'neutral')
            importance = scene.get('importance', 0.5)
            
            # 过滤敏感词
            dialogue = self._filter_sensitive(dialogue)
            
            # 决定音频模式
            audio_mode, reason = self._decide_audio_mode(
                dialogue, emotion, importance
            )
            
            segment = SceneSegment(
                scene_id=scene.get('scene_id', i + 1),  # 修复：从输入读取scene_id
                start_time=scene.get('start_time', 0),
                end_time=scene.get('end_time', 0),
                dialogue=dialogue,
                narration="",  # 稍后生成
                audio_mode=audio_mode,
                importance=importance,
                emotion=emotion,
                reason=reason
            )
            
            result.append(segment)
        
        # 打印统计
        orig = sum(1 for s in result if s.audio_mode == AudioMode.ORIGINAL)
        voice = sum(1 for s in result if s.audio_mode == AudioMode.VOICEOVER)
        skip = sum(1 for s in result if s.audio_mode == AudioMode.SKIP)
        print(f"   原声: {orig}, 解说: {voice}, 跳过: {skip}")
        
        return result
    
    def _decide_audio_mode(
        self, 
        dialogue: str, 
        emotion: str, 
        importance: float
    ) -> Tuple[AudioMode, str]:
        """
        决定场景的音频模式
        
        电视剧模式：更倾向于解说（讲故事）
        电影模式：更倾向于原声（保留经典）
        """
        # 强情感 → 原声（两种模式都保留）
        if emotion in ['angry', 'sad', 'excited', 'happy', 'fear']:
            return AudioMode.ORIGINAL, f"强情感场景({emotion})"
        
        # 根据媒体类型调整阈值
        if self.media_type == "tv":
            # 电视剧模式：更多解说
            original_threshold = 0.7  # 只有高重要性才用原声
            voiceover_threshold = 0.25  # 中等以上都用解说
            dialogue_threshold = 20  # 较长对话才用原声
        else:
            # 电影模式：更多原声
            original_threshold = 0.5  # 中等以上用原声
            voiceover_threshold = 0.35  # 较低才用解说
            dialogue_threshold = 12  # 短对话也用原声
        
        # 有对话的场景
        if dialogue and len(dialogue) > dialogue_threshold:
            if importance >= original_threshold:
                return AudioMode.ORIGINAL, "重要对话"
            else:
                return AudioMode.VOICEOVER, "用解说概括对话"
        
        # 高重要性 → 原声
        if importance >= original_threshold:
            return AudioMode.ORIGINAL, "高重要性场景"
        
        # 中等重要性 → 解说
        if importance >= voiceover_threshold:
            return AudioMode.VOICEOVER, "过渡场景,用解说"
        
        # 低重要性 → 跳过
        return AudioMode.SKIP, "低重要性,跳过"
    
    def _generate_narrations(
        self, 
        scenes: List[SceneSegment],
        plot_summary: str,
        style: str
    ) -> List[SceneSegment]:
        """为解说场景生成文案"""
        
        for scene in scenes:
            if scene.audio_mode != AudioMode.VOICEOVER:
                continue
            
            # 生成解说
            narration = self._generate_single_narration(
                scene, plot_summary, style
            )
            
            # 质量检查
            if self._is_low_quality(narration):
                # 低质量，改为原声
                scene.audio_mode = AudioMode.ORIGINAL
                scene.reason = "解说质量不佳,改用原声"
            else:
                scene.narration = narration
        
        return scenes
    
    def _generate_single_narration(
        self, 
        scene: SceneSegment,
        plot_summary: str,
        style: str
    ) -> str:
        """
        生成单个场景的解说
        
        核心：基于对话内容生成，不是泛泛而谈
        """
        dialogue = scene.dialogue
        
        if not dialogue:
            return ""
        
        # 尝试AI生成
        if self.llm_model:
            narration = self._ai_generate_narration(dialogue, style)
            if narration and not self._is_low_quality(narration):
                return narration
        
        # 备用：基于对话内容生成更好的解说
        # 关键：要概括，不是截取
        
        # 根据情感生成不同风格的解说
        if scene.emotion == 'angry':
            templates = [
                f"双方发生了激烈的争执",
                f"气氛一下子紧张起来",
                f"冲突在此刻爆发",
            ]
        elif scene.emotion == 'sad':
            templates = [
                f"气氛变得沉重起来",
                f"悲伤的情绪蔓延开来",
                f"这一幕令人动容",
            ]
        elif scene.emotion == 'happy':
            templates = [
                f"气氛变得轻松愉快",
                f"难得的温馨时刻",
                f"大家都露出了笑容",
            ]
        elif scene.emotion == 'fear':
            templates = [
                f"紧张的气氛让人窒息",
                f"危险正在逼近",
                f"所有人都屏住了呼吸",
            ]
        else:
            # neutral - 根据对话内容生成
            if len(dialogue) > 30:
                # 有较长对话，提取关键信息
                # 找到第一个完整句子
                for punct in ['。', '！', '？', '，']:
                    idx = dialogue.find(punct)
                    if idx > 5 and idx < 50:
                        return dialogue[:idx+1]
                return dialogue[:40] + "..."
            else:
                templates = [
                    f"故事继续发展",
                    f"情节推进中",
                ]
        
        import random
        return random.choice(templates)
    
    def _ai_summarize(self, text: str) -> str:
        """用AI总结文本"""
        if not self.llm_model:
            return ""
        
        try:
            import ollama
            
            prompt = f"""请用一句话总结以下对话的主要剧情（不超过100字）：

{text[:2000]}

总结："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_predict': 150, 'temperature': 0.3}
            )
            
            result = response['message']['content'].strip()
            return self._filter_sensitive(result)
            
        except Exception as e:
            return ""
    
    def _ai_generate_narration(self, dialogue: str, style: str) -> str:
        """用AI生成解说（区分电视剧/电影模式）"""
        if not self.llm_model:
            return ""
        
        try:
            import ollama
            
            # 构建上下文
            if self.media_type == "tv" and hasattr(self, 'episode_plot') and self.episode_plot:
                context = f"""本集剧情背景：{self.episode_plot[:200]}

当前场景对话：
{dialogue[:300]}"""
                task = f"为这个电视剧片段生成一句{style}风格的解说（20-40字），要结合本集剧情背景"
            else:
                context = f"对话内容：{dialogue[:300]}"
                task = f"为这个片段生成一句{style}风格的解说（15-30字）"
            
            prompt = f"""你是专业的视频解说员。{task}。

{context}

要求：
1. 概括对话内容，讲述正在发生的事情
2. 语言自然流畅，像真人讲故事
3. 禁止使用"紧张的场面"、"紧张的一幕"、"精彩画面"等空洞描述
4. 禁止涉及任何政治人物或敏感内容
5. 可以适当加入角色名字（如果能从对话中识别）

直接输出解说内容，不要加任何前缀："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_predict': 100, 'temperature': 0.65}
            )
            
            result = response['message']['content'].strip()
            
            # 清理格式
            result = result.replace('解说：', '').replace('解说:', '')
            result = result.replace('旁白：', '').replace('旁白:', '')
            result = result.strip('"\'""''')
            
            # 移除可能的数字序号
            import re
            result = re.sub(r'^[\d]+[\.、]\s*', '', result)
            
            return self._filter_sensitive(result)
            
        except Exception as e:
            return ""
    
    def _optimize_continuity(self, scenes: List[SceneSegment]) -> List[SceneSegment]:
        """优化剧情连贯性"""
        # 规则1：不能连续超过N个解说场景（会让观众疲劳）
        max_consecutive = 7 if self.media_type == "tv" else 4  # 电视剧允许更多连续解说
        consecutive_voiceover = 0
        
        for scene in scenes:
            if scene.audio_mode == AudioMode.VOICEOVER:
                consecutive_voiceover += 1
                if consecutive_voiceover > max_consecutive and scene.dialogue:
                    # 强制改为原声（插入原声让观众休息）
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.reason = "防止连续解说,插入原声"
                    consecutive_voiceover = 0
            else:
                consecutive_voiceover = 0
        
        # 规则2：确保最低原声比例
        orig_count = sum(1 for s in scenes if s.audio_mode == AudioMode.ORIGINAL)
        total = sum(1 for s in scenes if s.audio_mode != AudioMode.SKIP)
        
        if total > 0 and orig_count / total < self.min_original_ratio:
            # 原声比例太低，将部分解说改为原声（选重要性高的）
            voiceover_scenes = [s for s in scenes if s.audio_mode == AudioMode.VOICEOVER]
            voiceover_scenes.sort(key=lambda x: x.importance, reverse=True)
            
            need_convert = int(total * self.min_original_ratio) - orig_count
            for i, scene in enumerate(voiceover_scenes):
                if i >= need_convert:
                    break
                if scene.dialogue:
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.reason = "增加原声比例"
        
        return scenes
    
    def _compile_narration_text(self, scenes: List[SceneSegment]) -> str:
        """编译完整解说文本（供TTS使用）"""
        narrations = []
        
        for scene in scenes:
            if scene.audio_mode == AudioMode.VOICEOVER and scene.narration:
                narrations.append(scene.narration)
        
        return "\n".join(narrations)
    
    def _filter_sensitive(self, text: str) -> str:
        """过滤敏感词"""
        if not text:
            return ""
        
        result = text
        for word in SENSITIVE_WORDS:
            if word in result:
                result = result.replace(word, "")
        
        return result.strip()
    
    def _is_low_quality(self, text: str) -> bool:
        """检查是否是低质量内容"""
        if not text or len(text) < 5:
            return True
        
        for pattern in BAD_PATTERNS:
            if pattern in text:
                return True
        
        return False


def create_production_timeline(
    scenes: List[SceneSegment]
) -> List[Dict]:
    """
    创建最终制作时间线
    
    返回格式：
    [
        {
            'scene_id': 1,
            'source_start': 0.0,
            'source_end': 30.0,
            'output_start': 0.0,
            'output_end': 30.0,
            'audio_mode': 'original',  # or 'voiceover'
            'narration': '...',  # 如果是解说模式
            'dialogue': '...',   # 原始对话
        },
        ...
    ]
    """
    timeline = []
    output_time = 0.0
    
    for scene in scenes:
        if scene.audio_mode == AudioMode.SKIP:
            continue
        
        item = {
            'scene_id': scene.scene_id,
            'source_start': scene.start_time,
            'source_end': scene.end_time,
            'output_start': output_time,
            'output_end': output_time + scene.duration,
            'audio_mode': scene.audio_mode.value,
            'narration': scene.narration,
            'dialogue': scene.dialogue,
            'emotion': scene.emotion,
            'reason': scene.reason,
        }
        
        timeline.append(item)
        output_time += scene.duration
    
    return timeline


# 测试
if __name__ == "__main__":
    engine = NarrationEngine(use_ai=True)
    
    # 模拟场景
    test_scenes = [
        {'start_time': 0, 'end_time': 30, 'dialogue': '你是谁？为什么要来这里？', 'emotion': 'angry', 'importance': 0.9},
        {'start_time': 30, 'end_time': 60, 'dialogue': '我有话要告诉你', 'emotion': 'neutral', 'importance': 0.5},
        {'start_time': 60, 'end_time': 90, 'dialogue': '', 'emotion': 'neutral', 'importance': 0.2},
        {'start_time': 90, 'end_time': 120, 'dialogue': '这件事情非常重要，你必须知道真相', 'emotion': 'sad', 'importance': 0.8},
    ]
    
    segments, narration = engine.analyze_and_generate(test_scenes, "测试剧", "幽默")
    
    print("\n最终时间线:")
    for seg in segments:
        mode = "🔊原声" if seg.audio_mode == AudioMode.ORIGINAL else ("🎙️解说" if seg.audio_mode == AudioMode.VOICEOVER else "🔇跳过")
        print(f"  {seg.start_time:.0f}s-{seg.end_time:.0f}s: {mode} - {seg.reason}")

