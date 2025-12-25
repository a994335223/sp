# core/narration_engine.py - 解说引擎 v5.6 (分层生成+上下文感知版)
"""
SmartVideoClipper - 智能解说引擎 v5.6

v5.6 核心改进：
1. 分层生成：先生成故事框架，再按框架生成场景解说
2. 上下文窗口：每个场景考虑前2后2场景
3. 动态比例：根据场景特征自动计算解说比例(30%-75%)
4. 静音处理：检测并通过AI扩展填充静音段落
5. 钩子开场：自动生成吸引人的开场白
6. 悬念结尾：自动生成引发期待的结尾

v5.5基础保留：
- 批量生成解说（10场景/批）
- 移除模板，全部AI生成
- num_predict=2000确保完整输出

三种音频模式：
- [ORIGINAL] 原声场景：精彩对话、情感爆发、动作高潮
- [VOICEOVER] 解说场景：过渡、背景交代、快进
- [SKIP] 跳过场景：无意义、重复、拖沓
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 尝试加载配置
try:
    from config import TV_VOICEOVER_RATIO, MOVIE_VOICEOVER_RATIO, MIN_ORIGINAL_RATIO
except ImportError:
    TV_VOICEOVER_RATIO = 0.60
    MOVIE_VOICEOVER_RATIO = 0.40
    MIN_ORIGINAL_RATIO = 0.25

# v5.6新增：导入新模块
try:
    from core.story_framework import StoryFrameworkGenerator, FrameworkSegment
    from core.dynamic_ratio import DynamicRatioCalculator, calculate_optimal_ratio
    from core.silence_handler import SilenceHandler
    from core.hook_generator import HookGenerator
    MODULES_V56_AVAILABLE = True
except ImportError:
    MODULES_V56_AVAILABLE = False

# 敏感词列表
SENSITIVE_WORDS = [
    "习近平", "胡锦涛", "江泽民", "毛泽东", "邓小平", "温家宝", "李克强",
    "习主席", "总书记", "国家主席", "中央领导", "共产党", "国民党", 
    "民进党", "法轮功", "六四", "天安门", "台独", "藏独", "疆独", "港独",
]

# 低质量内容检测 - 这些绝对不能作为解说出现！
BAD_PATTERNS = [
    "紧张的场面", "紧张的一幕", "此刻紧张", "画面一转，紧张",
    "未知场景", "unknown", "场景1", "场景2",
    "故事继续发展", "情节推进中", "剧情推进", "故事推进",
    "接下来", "然后", "紧接着",
    "精彩画面", "精彩片段", "精彩镜头",
    "重要场景", "关键场景", "这一幕",
    "解说文本", "解说词", "旁白",
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


# ============================================================
# v5.5: 移除模板，全部使用AI生成
# ============================================================
# 注意：不再使用本地模板，实测证明批量AI生成成功率100%


class NarrationEngine:
    """
    智能解说引擎 v5.6 (分层生成+上下文感知版)
    
    核心职责：
    1. 生成故事框架（分层生成第1层）
    2. 根据框架+上下文生成场景解说（第2层）
    3. 动态计算解说比例（替代固定60%）
    4. 检测并处理静音段落
    5. 生成钩子开场和悬念结尾
    
    v5.6改进：
    - 分层生成：框架→解说
    - 上下文窗口：前2后2场景
    - 动态比例：30%-75%自动计算
    - 静音处理：AI扩展填充
    - 钩子+悬念：自动生成
    """
    
    def __init__(self, use_ai: bool = True, media_type: str = "tv", episode: int = 1, total_episodes: int = 1):
        """
        初始化解说引擎
        
        参数：
            use_ai: 是否使用AI生成
            media_type: 媒体类型 ("tv" 电视剧, "movie" 电影)
            episode: 集数/部数
            total_episodes: 总集数
        """
        self.use_ai = use_ai
        self.llm_model = None
        self.media_type = media_type
        self.episode = episode
        self.total_episodes = total_episodes
        self.episode_plot = ""  # 分集剧情
        self.title = ""  # 作品名称
        self.main_character = ""  # 主角名称
        
        # v5.6新增：故事框架
        self.story_framework = []
        
        # v5.6新增：钩子和结尾
        self.hook_opening = ""
        self.suspense_ending = ""
        
        # 动态比例（v5.6改进：不再固定）
        self.voiceover_ratio = 0.55  # 默认值，会被动态计算覆盖
        self.min_original_ratio = MIN_ORIGINAL_RATIO
        
        # 尝试加载LLM
        if use_ai:
            self._init_llm()
        
        # v5.6新增：初始化子模块
        self._init_v56_modules()
    
    def _init_llm(self):
        """初始化LLM模型"""
        try:
            import ollama
            models = ollama.list()
            
            # 保存完整模型名（包括:tag）
            available = []
            for model in models.get('models', []):
                name = model.get('name', '') or model.get('model', '')
                if name:
                    available.append(name)  # 保留完整名称如 qwen3:8b
            
            # 按优先级选择
            priority = ['qwen3', 'qwen2.5', 'qwen', 'llama3', 'gemma', 'mistral']
            for p in priority:
                for a in available:
                    if p in a.lower():
                        self.llm_model = a  # 使用完整名称
                        print(f"[LLM] 使用模型: {self.llm_model}")
                        return
            
            if available:
                self.llm_model = available[0]
                print(f"[LLM] 使用模型: {self.llm_model}")
        except Exception as e:
            print(f"[LLM] 初始化失败: {e}")
            self.llm_model = None
    
    def _init_v56_modules(self):
        """v5.6新增：初始化子模块"""
        self.framework_generator = None
        self.ratio_calculator = None
        self.silence_handler = None
        self.hook_generator = None
        
        if not MODULES_V56_AVAILABLE:
            print("[Engine] v5.6模块未加载，使用兼容模式")
            return
        
        try:
            # 故事框架生成器
            self.framework_generator = StoryFrameworkGenerator(self.llm_model)
            
            # 动态比例计算器
            self.ratio_calculator = DynamicRatioCalculator(self.media_type)
            
            # 静音处理器
            self.silence_handler = SilenceHandler(self.llm_model)
            
            # 钩子生成器
            self.hook_generator = HookGenerator(self.llm_model)
            
            print("[Engine] v5.6模块初始化成功")
        except Exception as e:
            print(f"[Engine] v5.6模块初始化异常: {e}")
    
    def analyze_and_generate(
        self,
        scenes: List[Dict],
        title: str = "",
        style: str = "幽默",
        episode_plot: str = "",
        main_character: str = ""
    ) -> Tuple[List[SceneSegment], str]:
        """
        分析场景并生成解说 v5.6
        
        参数：
            scenes: 场景列表
            title: 作品名称
            style: 解说风格
            episode_plot: 分集剧情
            main_character: 主角名称
        
        返回：(处理后的场景列表, 完整解说文本)
        """
        print("\n" + "="*60)
        print("[Engine] 智能解说引擎 v5.6 (分层生成+上下文感知版)")
        print("="*60)
        print(f"   作品: {title}")
        print(f"   类型: {'电视剧' if self.media_type == 'tv' else '电影'}")
        if self.media_type == "tv":
            print(f"   集数: 第{self.episode}集")
        print(f"   风格: {style}")
        print(f"   场景数: {len(scenes)}")
        print(f"   v5.6模块: {'已加载' if MODULES_V56_AVAILABLE else '未加载'}")
        print("="*60)
        
        # 保存基本信息
        self.episode_plot = episode_plot
        self.title = title
        self.main_character = main_character
        
        # Step 1: 理解整体剧情
        print("\n[Step 1] 理解剧情脉络...")
        plot_summary = self._understand_plot(scenes)
        print(f"   剧情概要: {plot_summary[:100]}...")
        
        # Step 1.5 [v5.6新增]: 生成故事框架
        if self.framework_generator:
            print("\n[Step 1.5] 生成故事框架 (v5.6)...")
            self.story_framework = self.framework_generator.generate_framework(
                title=title,
                media_type=self.media_type,
                episode=self.episode,
                plot_summary=plot_summary,
                scenes=scenes,
                total_episodes=self.total_episodes
            )
            print(f"   框架段落: {len(self.story_framework)}个")
        
        # Step 1.6 [v5.6新增]: 计算动态解说比例
        if self.ratio_calculator:
            print("\n[Step 1.6] 计算动态解说比例 (v5.6)...")
            self.voiceover_ratio, ratio_details = self.ratio_calculator.calculate_global_ratio(scenes)
            print(f"   动态比例: {self.voiceover_ratio*100:.0f}% (范围30%-75%)")
            if ratio_details.get('adjustments'):
                for adj in ratio_details['adjustments'][:3]:
                    print(f"      - {adj}")
        else:
            print(f"   目标解说比例: {self.voiceover_ratio*100:.0f}% (固定)")
        
        # Step 2: 标记场景类型
        print("\n[Step 2] 分析场景类型...")
        marked_scenes = self._mark_scenes(scenes)
        
        # Step 3: 生成解说（v5.6增强：上下文窗口）
        print("\n[Step 3] 生成解说文案 (v5.6上下文感知)...")
        final_scenes = self._generate_narrations_v56(marked_scenes, scenes, plot_summary, style)
        
        # Step 4: 确保达到目标比例
        print("\n[Step 4] 调整解说比例...")
        final_scenes = self._ensure_voiceover_ratio(final_scenes)
        
        # Step 4.5 [v5.6新增]: 处理静音段落
        if self.silence_handler:
            print("\n[Step 4.5] 处理静音段落 (v5.6)...")
            final_scenes = self._process_silence_gaps(final_scenes, plot_summary, style)
        
        # Step 5: 优化连贯性
        print("\n[Step 5] 优化剧情连贯性...")
        final_scenes = self._optimize_continuity(final_scenes)
        
        # Step 5.5 [v5.6新增]: 生成钩子开场和悬念结尾
        if self.hook_generator:
            print("\n[Step 5.5] 生成钩子开场和悬念结尾 (v5.6)...")
            self._generate_hook_and_ending(plot_summary, style, len(scenes))
        
        # 统计
        original_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.ORIGINAL)
        voiceover_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.VOICEOVER)
        skip_count = sum(1 for s in final_scenes if s.audio_mode == AudioMode.SKIP)
        active_count = original_count + voiceover_count
        
        total_duration = sum(s.duration for s in final_scenes if s.audio_mode != AudioMode.SKIP)
        
        print("\n" + "="*60)
        print("[STATS] 分析结果 (v5.5):")
        if active_count > 0:
            print(f"   [ORIGINAL] 原声场景: {original_count} ({original_count*100//active_count}%)")
            print(f"   [VOICEOVER] 解说场景: {voiceover_count} ({voiceover_count*100//active_count}%)")
        print(f"   [SKIP] 跳过场景: {skip_count}")
        print(f"   [DURATION] 预计时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        print("="*60)
        
        # 生成完整解说文本
        full_narration = self._compile_narration_text(final_scenes)
        
        return final_scenes, full_narration
    
    def _understand_plot(self, scenes: List[Dict]) -> str:
        """理解整体剧情"""
        all_dialogues = []
        for scene in scenes:
            dialogue = scene.get('dialogue', '').strip()
            if dialogue and len(dialogue) > 10:
                dialogue = self._filter_sensitive(dialogue)
                if dialogue:
                    all_dialogues.append(dialogue)
        
        if not all_dialogues:
            return "无法识别剧情内容"
        
        # 用AI总结
        if self.llm_model:
            combined = "\n".join(all_dialogues[:50])
            summary = self._ai_summarize(combined)
            if summary:
                return summary
        
        # 备用：简单拼接
        return " ".join(all_dialogues[:10])[:500]
    
    def _mark_scenes(self, scenes: List[Dict]) -> List[SceneSegment]:
        """
        标记每个场景的类型
        
        v5.3改进：使用更宽松的阈值，确保更多场景被标记为解说
        """
        result = []
        
        for i, scene in enumerate(scenes):
            dialogue = scene.get('dialogue', '').strip()
            emotion = scene.get('emotion', 'neutral')
            importance = scene.get('importance', 0.5)
            
            dialogue = self._filter_sensitive(dialogue)
            
            # 决定音频模式（使用宽松阈值）
            audio_mode, reason = self._decide_audio_mode(
                dialogue, emotion, importance
            )
            
            segment = SceneSegment(
                scene_id=scene.get('scene_id', i + 1),
                start_time=scene.get('start_time', 0),
                end_time=scene.get('end_time', 0),
                dialogue=dialogue,
                narration="",
                audio_mode=audio_mode,
                importance=importance,
                emotion=emotion,
                reason=reason
            )
            
            result.append(segment)
        
        # 统计
        orig = sum(1 for s in result if s.audio_mode == AudioMode.ORIGINAL)
        voice = sum(1 for s in result if s.audio_mode == AudioMode.VOICEOVER)
        skip = sum(1 for s in result if s.audio_mode == AudioMode.SKIP)
        print(f"   初始标记: 原声{orig}, 解说{voice}, 跳过{skip}")
        
        return result
    
    def _decide_audio_mode(
        self, 
        dialogue: str, 
        emotion: str, 
        importance: float
    ) -> Tuple[AudioMode, str]:
        """
        决定场景的音频模式
        
        v5.3改进：
        - 电视剧模式使用更宽松阈值，让更多场景成为解说
        - 只有极高重要性或强情感才保留原声
        """
        # 强情感 → 原声（但比例要控制）
        if emotion in ['angry', 'sad', 'excited'] and importance >= 0.7:
            return AudioMode.ORIGINAL, f"强情感场景({emotion})"
        
        # 根据媒体类型调整阈值
        if self.media_type == "tv":
            # 电视剧模式：大幅放宽解说条件
            original_threshold = 0.85   # 极高重要性才用原声
            voiceover_threshold = 0.15  # 低重要性以上都用解说
            dialogue_threshold = 40     # 很长对话才用原声
        else:
            # 电影模式
            original_threshold = 0.65
            voiceover_threshold = 0.30
            dialogue_threshold = 25
        
        # 极高重要性 + 有对话 → 原声
        if importance >= original_threshold and dialogue and len(dialogue) > dialogue_threshold:
            return AudioMode.ORIGINAL, "重要精彩对话"
        
        # 有对话但不是极高重要性 → 解说
        if dialogue and len(dialogue) > 5:
            return AudioMode.VOICEOVER, "用解说概括对话"
        
        # 无对话但重要性中等 → 解说
        if importance >= voiceover_threshold:
            return AudioMode.VOICEOVER, "过渡场景用解说"
        
        # 低重要性 → 跳过
        return AudioMode.SKIP, "低重要性跳过"
    
    def _generate_narrations(
        self, 
        scenes: List[SceneSegment],
        plot_summary: str,
        style: str
    ) -> List[SceneSegment]:
        """
        批量生成解说文案 v5.5
        
        实测数据对比：
        - 单次×608：102秒/10个，成功率50%
        - 批量×61：18秒/10个，成功率100%
        
        策略：
        1. 将场景分成10个一批
        2. 每批用一次AI调用生成JSON数组
        3. 失败场景用AI总结对话（非模板）
        """
        import time
        import json
        import re
        from datetime import datetime
        
        def log(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
        
        # 收集需要解说的场景
        voiceover_scenes = [s for s in scenes if s.audio_mode == AudioMode.VOICEOVER]
        voiceover_count = len(voiceover_scenes)
        
        if voiceover_count == 0:
            log("[Narration] 无需生成解说")
            return scenes
        
        start_time = time.time()
        batch_size = 10  # 每批10个场景
        batch_count = (voiceover_count + batch_size - 1) // batch_size
        
        log(f"[Narration] ========== 批量生成解说 v5.5 ==========")
        log(f"[Narration] 场景总数: {voiceover_count}")
        log(f"[Narration] 批次数量: {batch_count} (每批{batch_size}个)")
        log(f"[Narration] AI模型: {self.llm_model or '未加载'}")
        log(f"[Narration] 剧情概要: {plot_summary[:80]}...")
        
        generated = 0
        fallback_used = 0
        failed = 0
        
        # 分批处理
        for batch_idx in range(batch_count):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, voiceover_count)
            batch_scenes = voiceover_scenes[batch_start:batch_end]
            
            elapsed = time.time() - start_time
            log(f"[Narration] 批次 {batch_idx+1}/{batch_count} | "
                f"场景 {batch_start+1}-{batch_end}/{voiceover_count} | "
                f"耗时: {elapsed:.0f}秒")
            
            # 批量生成
            if self.llm_model:
                narrations = self._batch_generate_narrations(batch_scenes, plot_summary, style)
            else:
                narrations = []
            
            # 分配结果
            for i, scene in enumerate(batch_scenes):
                if i < len(narrations) and narrations[i]:
                    narration = narrations[i]
                    # 质量检查
                    if len(narration) >= 5 and not self._is_low_quality(narration):
                        scene.narration = narration
                        generated += 1
                        continue
                
                # 批量失败的场景，用AI总结对话
                fallback = self._ai_summarize_dialogue(scene.dialogue)
                if fallback and len(fallback) >= 5:
                    scene.narration = fallback
                    fallback_used += 1
                else:
                    # 最后兜底：保留原声
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.reason = "AI生成失败,改用原声"
                    failed += 1
        
        total_time = time.time() - start_time
        success_rate = (generated + fallback_used) / voiceover_count * 100 if voiceover_count > 0 else 0
        
        log(f"[Narration] ========== 生成完成 ==========")
        log(f"[Narration] 批量成功: {generated} ({generated*100//voiceover_count}%)")
        log(f"[Narration] AI总结: {fallback_used} ({fallback_used*100//voiceover_count}%)")
        log(f"[Narration] 失败转原声: {failed}")
        log(f"[Narration] 总成功率: {success_rate:.1f}%")
        log(f"[Narration] 总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
        log(f"[Narration] 平均速度: {voiceover_count/total_time:.1f}个/秒")
        
        return scenes
    
    def _generate_narrations_v56(
        self, 
        marked_scenes: List[SceneSegment],
        original_scenes: List[Dict],
        plot_summary: str,
        style: str
    ) -> List[SceneSegment]:
        """
        v5.6增强版解说生成（带上下文窗口）
        
        改进：
        1. 每个场景考虑前2后2场景的上下文
        2. 使用故事框架指导生成
        3. 计算目标字数以匹配场景时长
        """
        import time
        from datetime import datetime
        
        def log(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
        
        # 收集需要解说的场景
        voiceover_scenes = [s for s in marked_scenes if s.audio_mode == AudioMode.VOICEOVER]
        voiceover_count = len(voiceover_scenes)
        
        if voiceover_count == 0:
            log("[Narration] 无需生成解说")
            return marked_scenes
        
        start_time = time.time()
        batch_size = 10
        batch_count = (voiceover_count + batch_size - 1) // batch_size
        
        log(f"[Narration] ========== v5.6批量生成 (上下文感知) ==========")
        log(f"[Narration] 场景总数: {voiceover_count}")
        log(f"[Narration] 批次数量: {batch_count}")
        log(f"[Narration] 故事框架: {len(self.story_framework)}段")
        
        generated = 0
        fallback_used = 0
        failed = 0
        
        # 构建场景ID到索引的映射
        scene_idx_map = {s.scene_id: i for i, s in enumerate(marked_scenes)}
        
        # 分批处理
        for batch_idx in range(batch_count):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, voiceover_count)
            batch_scenes = voiceover_scenes[batch_start:batch_end]
            
            elapsed = time.time() - start_time
            log(f"[Narration] 批次 {batch_idx+1}/{batch_count} | "
                f"场景 {batch_start+1}-{batch_end}/{voiceover_count} | "
                f"耗时: {elapsed:.0f}秒")
            
            # v5.6改进：构建带上下文的批量请求
            if self.llm_model:
                narrations = self._batch_generate_with_context(
                    batch_scenes, marked_scenes, original_scenes,
                    plot_summary, style
                )
            else:
                narrations = []
            
            # 分配结果
            for i, scene in enumerate(batch_scenes):
                if i < len(narrations) and narrations[i]:
                    narration = narrations[i]
                    if len(narration) >= 5 and not self._is_low_quality(narration):
                        scene.narration = narration
                        generated += 1
                        continue
                
                # 备用：AI总结对话
                fallback = self._ai_summarize_dialogue(scene.dialogue)
                if fallback and len(fallback) >= 5:
                    scene.narration = fallback
                    fallback_used += 1
                else:
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.reason = "AI生成失败,改用原声"
                    failed += 1
        
        total_time = time.time() - start_time
        success_rate = (generated + fallback_used) / voiceover_count * 100 if voiceover_count > 0 else 0
        
        log(f"[Narration] ========== 生成完成 ==========")
        log(f"[Narration] 批量成功: {generated} ({generated*100//max(1,voiceover_count)}%)")
        log(f"[Narration] AI总结: {fallback_used}")
        log(f"[Narration] 失败转原声: {failed}")
        log(f"[Narration] 总成功率: {success_rate:.1f}%")
        log(f"[Narration] 总耗时: {total_time:.1f}秒")
        
        return marked_scenes
    
    def _batch_generate_with_context(
        self,
        batch_scenes: List[SceneSegment],
        all_scenes: List[SceneSegment],
        original_scenes: List[Dict],
        plot_summary: str,
        style: str
    ) -> List[str]:
        """
        v5.6：带上下文窗口的批量生成
        
        每个场景包含：
        - 对应的故事框架段落
        - 前2个场景摘要
        - 后2个场景摘要
        - 目标字数
        """
        if not self.llm_model:
            return []
        
        try:
            import ollama
            
            # 构建场景ID到索引的映射
            scene_id_to_idx = {s.scene_id: i for i, s in enumerate(all_scenes)}
            
            # 构建批量prompt
            scene_list = []
            for i, scene in enumerate(batch_scenes):
                scene_idx = scene_id_to_idx.get(scene.scene_id, 0)
                
                # 获取框架指导
                framework_hint = ""
                if self.story_framework and self.framework_generator:
                    segment = self.framework_generator.get_segment_for_scene(
                        scene.scene_id, self.story_framework
                    )
                    if segment:
                        framework_hint = f"[{segment.theme}|{segment.emotion}] "
                
                # 获取前后场景（上下文窗口）
                context_parts = []
                
                # 前2个场景
                for offset in [-2, -1]:
                    prev_idx = scene_idx + offset
                    if 0 <= prev_idx < len(all_scenes):
                        prev_scene = all_scenes[prev_idx]
                        prev_dialogue = prev_scene.dialogue[:30] if prev_scene.dialogue else "(无)"
                        context_parts.append(f"前{-offset}:{prev_dialogue}")
                
                # 当前对话
                dialogue = scene.dialogue[:80] if scene.dialogue else "(无对话)"
                
                # 后2个场景
                for offset in [1, 2]:
                    next_idx = scene_idx + offset
                    if next_idx < len(all_scenes):
                        next_scene = all_scenes[next_idx]
                        next_dialogue = next_scene.dialogue[:30] if next_scene.dialogue else "(无)"
                        context_parts.append(f"后{offset}:{next_dialogue}")
                
                # 计算目标字数
                target_chars = int(scene.duration * 4)  # 4字/秒
                target_chars = max(15, min(50, target_chars))
                
                # 构建场景描述
                context_str = " | ".join(context_parts) if context_parts else ""
                scene_desc = f"{i+1}. {framework_hint}[{target_chars}字] {dialogue}"
                if context_str:
                    scene_desc += f" (上下文:{context_str})"
                
                scene_list.append(scene_desc)
            
            scenes_text = "\n".join(scene_list)
            
            prompt = f"""为以下{len(batch_scenes)}个场景各生成一句{style}解说。

剧情背景：{plot_summary[:150]}

场景列表（含上下文和目标字数）：
{scenes_text}

要求：
1. 每句解说按[目标字数]生成
2. {style}风格
3. 结合上下文，承上启下
4. 不要复述对话原文
5. 直接输出JSON数组格式

输出格式：["解说1", "解说2", ...]"""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 2000,
                    'temperature': 0.6,
                }
            )
            
            # 提取内容
            msg = response.get('message', {})
            content = ""
            
            if hasattr(msg, 'content') and msg.content:
                content = msg.content.strip()
            elif hasattr(msg, 'thinking') and msg.thinking:
                content = msg.thinking.strip()
            
            if not content:
                return []
            
            # 解析JSON数组
            import json
            match = re.search(r'\[.*?\]', content, re.DOTALL)
            if match:
                try:
                    results = json.loads(match.group())
                    if isinstance(results, list):
                        cleaned = []
                        for r in results:
                            if isinstance(r, str):
                                r = r.strip().strip('"\'')
                                r = re.sub(r'^[\d]+[\.、]\s*', '', r)
                                cleaned.append(r)
                            else:
                                cleaned.append("")
                        return cleaned
                except json.JSONDecodeError:
                    pass
            
            # JSON解析失败，尝试按行分割
            lines = content.split('\n')
            results = []
            for line in lines:
                line = line.strip()
                line = re.sub(r'^[\d]+[\.、\)）]\s*', '', line)
                line = line.strip('"\'[]')
                if line and len(line) > 5 and len(line) < 60:
                    results.append(line)
            
            return results[:len(batch_scenes)]
            
        except Exception as e:
            print(f"[Narration] v5.6批量生成异常: {e}", flush=True)
            # 降级到v5.5方法
            return self._batch_generate_narrations(batch_scenes, plot_summary, style)
    
    def _process_silence_gaps(
        self,
        scenes: List[SceneSegment],
        plot_summary: str,
        style: str
    ) -> List[SceneSegment]:
        """
        v5.6新增：处理静音段落
        """
        if not self.silence_handler:
            return scenes
        
        # 转换为dict格式
        scene_dicts = []
        for s in scenes:
            scene_dicts.append({
                'scene_id': s.scene_id,
                'start_time': s.start_time,
                'end_time': s.end_time,
                'audio_mode': s.audio_mode.value,
                'narration': s.narration,
                'dialogue': s.dialogue,
                'emotion': s.emotion,
            })
        
        # 检测静音
        gaps = self.silence_handler.detect_silence_gaps(scene_dicts)
        
        if not gaps:
            print("   无静音段落")
            return scenes
        
        print(f"   检测到静音: {len(gaps)}处")
        
        # 处理静音
        gaps, expanded, adjusted = self.silence_handler.process_silence_gaps(
            gaps, scene_dicts, plot_summary, style
        )
        
        # 应用结果
        gap_map = {g.scene_id: g for g in gaps}
        for scene in scenes:
            if scene.scene_id in gap_map:
                gap = gap_map[scene.scene_id]
                if gap.expanded_narration:
                    scene.narration = gap.expanded_narration
        
        print(f"   AI扩展: {expanded}, 语速调整: {adjusted}")
        
        return scenes
    
    def _generate_hook_and_ending(self, plot_summary: str, style: str, total_scenes: int):
        """
        v5.6新增：生成钩子开场和悬念结尾
        """
        if not self.hook_generator:
            return
        
        # 生成钩子开场
        if self.hook_generator.should_add_hook(self.media_type, self.episode, self.total_episodes):
            duration_minutes = total_scenes * 5 // 60  # 粗略估算
            self.hook_opening = self.hook_generator.generate_hook(
                title=self.title,
                plot_summary=plot_summary,
                main_character=self.main_character,
                style=style,
                duration_minutes=max(5, duration_minutes)
            )
            print(f"   钩子开场: {self.hook_opening[:40]}...")
        
        # 生成悬念结尾
        should_add, ending_type = self.hook_generator.should_add_suspense(
            self.media_type, self.episode, self.total_episodes
        )
        if should_add:
            has_next = self.episode < self.total_episodes
            self.suspense_ending = self.hook_generator.generate_ending(
                title=self.title,
                plot_summary=plot_summary,
                ending_type=ending_type,
                main_character=self.main_character,
                style=style,
                has_next_episode=has_next
            )
            print(f"   {ending_type}结尾: {self.suspense_ending[:40]}...")
    
    def _batch_generate_narrations(
        self, 
        scenes: List[SceneSegment], 
        plot_summary: str, 
        style: str
    ) -> List[str]:
        """
        批量生成解说（一次AI调用生成多个）
        
        实测：批量生成比单次快5.8倍，成功率100%
        """
        if not self.llm_model:
            return []
        
        try:
            import ollama
            
            # 构建批量prompt
            scene_list = []
            for i, scene in enumerate(scenes):
                dialogue = scene.dialogue[:100] if scene.dialogue else "(无对话)"
                scene_list.append(f"{i+1}. {dialogue}")
            
            scenes_text = "\n".join(scene_list)
            
            prompt = f"""为以下{len(scenes)}个场景各生成一句{style}解说（15-30字）。

剧情背景：{plot_summary[:150]}

场景对话：
{scenes_text}

要求：
1. 每句解说15-30字
2. {style}风格
3. 直接输出JSON数组格式

输出格式：["解说1", "解说2", ...]"""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 2000,  # 批量需要更多token
                    'temperature': 0.6,
                }
            )
            
            # 提取内容
            msg = response.get('message', {})
            content = ""
            
            # 优先使用content
            if hasattr(msg, 'content') and msg.content:
                content = msg.content.strip()
            # content为空时尝试thinking
            elif hasattr(msg, 'thinking') and msg.thinking:
                content = msg.thinking.strip()
            
            if not content:
                return []
            
            # 解析JSON数组
            import re
            import json
            
            # 尝试找到JSON数组
            match = re.search(r'\[.*?\]', content, re.DOTALL)
            if match:
                try:
                    results = json.loads(match.group())
                    if isinstance(results, list):
                        # 清理每个结果
                        cleaned = []
                        for r in results:
                            if isinstance(r, str):
                                r = r.strip().strip('"\'')
                                r = re.sub(r'^[\d]+[\.、]\s*', '', r)
                                cleaned.append(r)
                            else:
                                cleaned.append("")
                        return cleaned
                except json.JSONDecodeError:
                    pass
            
            # JSON解析失败，尝试按行分割
            lines = content.split('\n')
            results = []
            for line in lines:
                line = line.strip()
                # 移除序号
                line = re.sub(r'^[\d]+[\.、\)）]\s*', '', line)
                line = line.strip('"\'[]')
                if line and len(line) > 5 and len(line) < 60:
                    results.append(line)
            
            return results[:len(scenes)]
            
        except Exception as e:
            print(f"[Narration] 批量生成异常: {e}", flush=True)
            return []
    
    def _ai_summarize_dialogue(self, dialogue: str) -> str:
        """
        用AI总结对话（备用方案）
        
        替代原来的模板方案，确保每个解说都是AI生成的
        """
        if not self.llm_model or not dialogue:
            return ""
        
        try:
            import ollama
            
            # 简短prompt，快速生成
            prompt = f"用15字概括这段对话：{dialogue[:100]}"
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 100,
                    'temperature': 0.5,
                }
            )
            
            msg = response.get('message', {})
            result = ""
            
            if hasattr(msg, 'content') and msg.content:
                result = msg.content.strip()
            elif hasattr(msg, 'thinking') and msg.thinking:
                # 从thinking提取最后一句
                lines = msg.thinking.strip().split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if line and 5 < len(line) < 40:
                        if not any(x in line for x in ['用户', '需要', '可能', '首先']):
                            result = line
                            break
            
            if result:
                result = result.strip('"\'')
                result = self._filter_sensitive(result)
            
            return result
            
        except Exception:
            return ""
    
    def _generate_fallback_narration(self, scene: SceneSegment, style: str) -> str:
        """
        备用解说生成 v5.5
        
        v5.5改进：不再使用模板，调用AI总结对话
        """
        return self._ai_summarize_dialogue(scene.dialogue)
    
    def _ensure_voiceover_ratio(self, scenes: List[SceneSegment]) -> List[SceneSegment]:
        """
        确保达到目标解说比例 v5.5
        
        v5.5改进：不再使用模板，调用AI生成
        """
        active_scenes = [s for s in scenes if s.audio_mode != AudioMode.SKIP]
        if not active_scenes:
            return scenes
        
        voiceover_count = sum(1 for s in active_scenes if s.audio_mode == AudioMode.VOICEOVER)
        total = len(active_scenes)
        
        current_ratio = voiceover_count / total if total > 0 else 0
        
        print(f"   当前解说比例: {current_ratio*100:.0f}%, 目标: {self.voiceover_ratio*100:.0f}%")
        
        if current_ratio < self.voiceover_ratio:
            # 需要增加解说场景
            need_convert = int(total * self.voiceover_ratio) - voiceover_count
            
            # 按重要性排序原声场景（低重要性优先转换）
            original_scenes = [s for s in active_scenes if s.audio_mode == AudioMode.ORIGINAL]
            original_scenes.sort(key=lambda x: x.importance)
            
            # 收集需要转换的场景
            to_convert = []
            for scene in original_scenes:
                if len(to_convert) >= need_convert:
                    break
                
                # 保留极高重要性场景的原声
                if scene.importance >= 0.85:
                    continue
                
                to_convert.append(scene)
            
            # 批量生成解说
            if to_convert and self.llm_model:
                narrations = self._batch_generate_narrations(to_convert, self.episode_plot or "", "幽默")
                
                converted = 0
                for i, scene in enumerate(to_convert):
                    if i < len(narrations) and narrations[i] and len(narrations[i]) >= 5:
                        scene.audio_mode = AudioMode.VOICEOVER
                        scene.narration = narrations[i]
                        scene.reason = "比例调整:原声→解说"
                        converted += 1
                    else:
                        # 单独AI总结
                        fallback = self._ai_summarize_dialogue(scene.dialogue)
                        if fallback and len(fallback) >= 5:
                            scene.audio_mode = AudioMode.VOICEOVER
                            scene.narration = fallback
                            scene.reason = "比例调整:原声→解说"
                            converted += 1
                
                print(f"   比例调整: 转换{converted}个场景为解说")
        
        return scenes
    
    def _ai_summarize(self, text: str) -> str:
        """
        用AI总结文本 v5.5
        
        修复：正确处理Message对象的属性访问
        """
        if not self.llm_model:
            return ""
        
        try:
            import ollama
            
            prompt = f"""用100字总结以下对话的主要剧情：

{text[:2000]}

剧情总结："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_predict': 500, 'temperature': 0.3}
            )
            
            # 获取内容（v5.5修复：正确访问Message对象属性）
            msg = response.get('message', {})
            result = ""
            
            # 优先使用content
            if hasattr(msg, 'content') and msg.content:
                result = msg.content.strip()
            # content为空时尝试thinking
            elif hasattr(msg, 'thinking') and msg.thinking:
                # 从thinking提取总结部分
                thinking = msg.thinking.strip()
                # 取最后几行作为结论
                lines = thinking.split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if line and 20 < len(line) < 150:
                        result = line
                        break
                if not result:
                    result = thinking[:200]
            
            return self._filter_sensitive(result)
            
        except Exception as e:
            return ""
    
    def _ai_generate_narration(self, dialogue: str, style: str) -> str:
        """
        用AI生成单条解说 v5.5
        
        注意：v5.5主要使用批量生成(_batch_generate_narrations)
        此函数保留作为备用或单场景处理
        
        修复：num_predict提升到500，正确访问Message属性
        """
        if not self.llm_model or not dialogue:
            return ""
        
        try:
            import ollama
            
            # 构建上下文
            if self.media_type == "tv" and self.episode_plot:
                context = f"剧情：{self.episode_plot[:100]}。对话：{dialogue[:150]}"
                task = f"生成{style}解说（15-30字）"
            else:
                context = f"对话：{dialogue[:150]}"
                task = f"生成{style}解说（10-25字）"
            
            prompt = f"""{task}

{context}

直接输出解说（一句话，不要解释）："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 500,  # v5.5: 增加到500确保thinking完成
                    'temperature': 0.5,
                    'top_p': 0.9,
                }
            )
            
            # v5.5修复：正确访问Message对象属性
            msg = response.get('message', {})
            result = ""
            
            # 优先使用content
            if hasattr(msg, 'content') and msg.content:
                result = msg.content.strip()
            # content为空时尝试thinking
            elif hasattr(msg, 'thinking') and msg.thinking:
                thinking = msg.thinking
                lines = thinking.split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if line and 5 < len(line) < 50:
                        if not any(x in line for x in ['用户', '需要', '可能', '首先', '接下来']):
                            result = line
                            break
            
            if not result:
                return ""
            
            # 清理格式
            result = result.replace('解说：', '').replace('解说:', '')
            result = result.replace('旁白：', '').replace('旁白:', '')
            result = result.strip('"\'""''')
            result = re.sub(r'^[\d]+[\.、]\s*', '', result)
            
            return self._filter_sensitive(result)
            
        except Exception as e:
            return ""
    
    def _optimize_continuity(self, scenes: List[SceneSegment]) -> List[SceneSegment]:
        """
        优化剧情连贯性
        """
        # 规则1：去除重复解说
        scenes = self._remove_duplicate_narrations(scenes)
        
        # 规则2：不能连续过多解说（但允许更多）
        max_consecutive = 10 if self.media_type == "tv" else 6
        consecutive_voiceover = 0
        
        for scene in scenes:
            if scene.audio_mode == AudioMode.VOICEOVER:
                consecutive_voiceover += 1
                if consecutive_voiceover > max_consecutive and scene.dialogue:
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.narration = ""
                    scene.reason = "防止连续解说"
                    consecutive_voiceover = 0
            else:
                consecutive_voiceover = 0
        
        return scenes
    
    def _remove_duplicate_narrations(self, scenes: List[SceneSegment]) -> List[SceneSegment]:
        """检测并去除重复解说"""
        last_narration = ""
        
        for scene in scenes:
            if scene.audio_mode != AudioMode.VOICEOVER:
                last_narration = ""
                continue
            
            if scene.narration:
                # 完全相同
                if scene.narration == last_narration:
                    scene.audio_mode = AudioMode.ORIGINAL
                    scene.reason = "去除重复解说"
                    scene.narration = ""
                    continue
                
                # 相似度检查
                if last_narration and len(scene.narration) > 5:
                    if scene.narration in last_narration or last_narration in scene.narration:
                        scene.audio_mode = AudioMode.ORIGINAL
                        scene.reason = "去除相似解说"
                        scene.narration = ""
                        continue
            
            last_narration = scene.narration
        
        return scenes
    
    def _compile_narration_text(self, scenes: List[SceneSegment]) -> str:
        """编译完整解说文本（v5.6增强：包含钩子和结尾）"""
        narrations = []
        
        # v5.6：添加钩子开场
        if self.hook_opening:
            narrations.append(f"[开场] {self.hook_opening}")
            narrations.append("")  # 空行分隔
        
        # 主体解说
        for scene in scenes:
            if scene.audio_mode == AudioMode.VOICEOVER and scene.narration:
                narrations.append(scene.narration)
        
        # v5.6：添加悬念结尾
        if self.suspense_ending:
            narrations.append("")  # 空行分隔
            narrations.append(f"[结尾] {self.suspense_ending}")
        
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


def create_production_timeline(scenes: List[SceneSegment]) -> List[Dict]:
    """创建最终制作时间线"""
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
    engine = NarrationEngine(use_ai=True, media_type="tv", episode=1)
    
    test_scenes = [
        {'start_time': 0, 'end_time': 30, 'dialogue': '你是谁？为什么要来这里？', 'emotion': 'angry', 'importance': 0.9},
        {'start_time': 30, 'end_time': 60, 'dialogue': '我有话要告诉你', 'emotion': 'neutral', 'importance': 0.5},
        {'start_time': 60, 'end_time': 90, 'dialogue': '', 'emotion': 'neutral', 'importance': 0.2},
        {'start_time': 90, 'end_time': 120, 'dialogue': '这件事情非常重要，你必须知道真相', 'emotion': 'sad', 'importance': 0.8},
    ]
    
    segments, narration = engine.analyze_and_generate(test_scenes, "测试剧", "幽默")
    
    print("\n最终时间线:")
    for seg in segments:
        mode = "[O]" if seg.audio_mode == AudioMode.ORIGINAL else ("[V]" if seg.audio_mode == AudioMode.VOICEOVER else "[S]")
        print(f"  {seg.start_time:.0f}s-{seg.end_time:.0f}s: {mode} - {seg.reason}")
        if seg.narration:
            print(f"      解说: {seg.narration}")
