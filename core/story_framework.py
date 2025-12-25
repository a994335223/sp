# core/story_framework.py - 故事框架生成器 v5.6
"""
SmartVideoClipper - 故事框架生成器 v5.6

核心功能：
1. 分析整集剧情，生成5-8段解说框架
2. 为每段标注情感基调和叙事目标
3. 提供全局视角指导局部解说生成

设计原则：
- 第一层生成：全局框架 → 确保整体连贯
- 为第二层（场景解说）提供上下文指导
"""

import os
import sys
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class FrameworkSegment:
    """框架段落"""
    segment_id: int           # 段落ID
    theme: str                # 段落主题（10字内）
    emotion: str              # 情感基调
    narrative_goal: str       # 叙事目标
    key_point: str            # 关键剧情点
    scene_range: Tuple[int, int]  # 对应场景范围 (start_idx, end_idx)
    
    def to_dict(self) -> Dict:
        return {
            'segment_id': self.segment_id,
            'theme': self.theme,
            'emotion': self.emotion,
            'narrative_goal': self.narrative_goal,
            'key_point': self.key_point,
            'scene_range': list(self.scene_range),
        }


# 情感基调选项
EMOTION_OPTIONS = ['紧张', '温情', '冲突', '悬疑', '高潮', '平静', '悲伤', '愤怒', '惊喜']

# 叙事目标选项
NARRATIVE_GOALS = ['铺垫', '转折', '升级', '爆发', '收尾', '过渡', '揭秘']


def log(msg: str):
    """统一日志输出"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class StoryFrameworkGenerator:
    """
    故事框架生成器 v5.6
    
    职责：
    1. 分析整集剧情和场景
    2. 生成5-8段解说框架
    3. 为每段标注情感和叙事目标
    """
    
    def __init__(self, llm_model: str = None):
        """
        初始化框架生成器
        
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
            
            priority = ['qwen3', 'qwen2.5', 'qwen', 'llama3', 'gemma', 'mistral']
            for p in priority:
                for a in available:
                    if p in a.lower():
                        self.llm_model = a
                        log(f"[Framework] LLM模型: {self.llm_model}")
                        return
            
            if available:
                self.llm_model = available[0]
                log(f"[Framework] LLM模型: {self.llm_model}")
        except Exception as e:
            log(f"[Framework] LLM初始化失败: {e}")
            self.llm_model = None
    
    def generate_framework(
        self,
        title: str,
        media_type: str,
        episode: int,
        plot_summary: str,
        scenes: List[Dict],
        total_episodes: int = 1
    ) -> List[FrameworkSegment]:
        """
        生成故事框架
        
        参数：
            title: 作品名称
            media_type: 媒体类型 (tv/movie)
            episode: 集数
            plot_summary: 剧情概要
            scenes: 场景列表
            total_episodes: 总集数
        
        返回：框架段落列表
        """
        log(f"[Framework] ========== 生成故事框架 v5.6 ==========")
        log(f"[Framework] 作品: {title}")
        log(f"[Framework] 类型: {'电视剧' if media_type == 'tv' else '电影'}")
        log(f"[Framework] 场景数: {len(scenes)}")
        
        # 提取场景摘要
        scene_summaries = self._extract_scene_summaries(scenes)
        log(f"[Framework] 提取场景摘要: {len(scene_summaries)}个")
        
        # 使用AI生成框架
        if self.llm_model:
            framework = self._ai_generate_framework(
                title, media_type, episode, plot_summary, 
                scene_summaries, len(scenes), total_episodes
            )
            if framework:
                log(f"[Framework] AI生成成功: {len(framework)}个段落")
                return framework
        
        # 备用：规则生成
        log(f"[Framework] 使用规则生成框架")
        return self._rule_based_framework(scenes, media_type)
    
    def _extract_scene_summaries(self, scenes: List[Dict]) -> List[str]:
        """提取场景摘要"""
        summaries = []
        for i, scene in enumerate(scenes):
            dialogue = scene.get('dialogue', '').strip()
            emotion = scene.get('emotion', 'neutral')
            importance = scene.get('importance', 0.5)
            
            if dialogue:
                # 截取前50字
                summary = dialogue[:50] + ('...' if len(dialogue) > 50 else '')
            else:
                summary = f"(无对话，{emotion}情绪)"
            
            summaries.append(f"[{i+1}] {summary}")
        
        return summaries
    
    def _ai_generate_framework(
        self,
        title: str,
        media_type: str,
        episode: int,
        plot_summary: str,
        scene_summaries: List[str],
        total_scenes: int,
        total_episodes: int
    ) -> Optional[List[FrameworkSegment]]:
        """使用AI生成框架"""
        if not self.llm_model:
            return None
        
        try:
            import ollama
            
            # 构建prompt
            media_type_cn = "电视剧" if media_type == "tv" else "电影"
            
            # 只取部分场景摘要避免prompt过长
            sample_scenes = scene_summaries[:30] if len(scene_summaries) > 30 else scene_summaries
            scenes_text = "\n".join(sample_scenes)
            
            prompt = f"""你是专业的电影解说文案策划师。请为以下剧集生成解说框架：

【作品信息】
- 名称：《{title}》第{episode}集
- 类型：{media_type_cn}
- 总场景数：{total_scenes}

【剧情概要】
{plot_summary[:500] if plot_summary else '(无剧情概要)'}

【部分场景摘要】
{scenes_text}

【要求】
1. 生成5-8个解说段落
2. 每段包含：主题、情感基调、叙事目标、关键点、场景范围
3. 情感可选：紧张/温情/冲突/悬疑/高潮/平静/悲伤/愤怒/惊喜
4. 叙事目标可选：铺垫/转折/升级/爆发/收尾/过渡/揭秘
5. 遵循"钩子开场→铺垫→冲突升级→高潮→悬念收尾"结构

【输出JSON格式】
[
  {{"segment_id": 1, "theme": "开场悬念", "emotion": "悬疑", "narrative_goal": "铺垫", "key_point": "xxx", "scene_start": 1, "scene_end": 10}},
  {{"segment_id": 2, "theme": "xxx", "emotion": "xxx", "narrative_goal": "转折", "key_point": "xxx", "scene_start": 11, "scene_end": 20}},
  ...
]

直接输出JSON数组，不要其他解释："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 2000,
                    'temperature': 0.4,
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
                return None
            
            # 解析JSON
            return self._parse_framework_json(content, total_scenes)
            
        except Exception as e:
            log(f"[Framework] AI生成异常: {e}")
            return None
    
    def _parse_framework_json(self, content: str, total_scenes: int) -> Optional[List[FrameworkSegment]]:
        """解析框架JSON"""
        try:
            # 尝试找到JSON数组
            match = re.search(r'\[[\s\S]*\]', content)
            if not match:
                return None
            
            json_str = match.group()
            data = json.loads(json_str)
            
            if not isinstance(data, list):
                return None
            
            segments = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                segment = FrameworkSegment(
                    segment_id=item.get('segment_id', len(segments) + 1),
                    theme=item.get('theme', f'段落{len(segments)+1}')[:15],
                    emotion=item.get('emotion', '平静'),
                    narrative_goal=item.get('narrative_goal', '过渡'),
                    key_point=item.get('key_point', '')[:100],
                    scene_range=(
                        max(1, item.get('scene_start', 1)),
                        min(total_scenes, item.get('scene_end', total_scenes))
                    )
                )
                segments.append(segment)
            
            # 验证段落数量
            if len(segments) < 3:
                return None
            
            return segments
            
        except json.JSONDecodeError:
            return None
        except Exception:
            return None
    
    def _rule_based_framework(self, scenes: List[Dict], media_type: str) -> List[FrameworkSegment]:
        """规则生成框架（备用方案）"""
        total = len(scenes)
        
        if total < 10:
            # 场景太少，简单分3段
            segments = [
                FrameworkSegment(1, "开场铺垫", "悬疑", "铺垫", "故事开始", (1, total//3)),
                FrameworkSegment(2, "情节发展", "紧张", "升级", "冲突展开", (total//3+1, total*2//3)),
                FrameworkSegment(3, "高潮收尾", "高潮", "收尾", "故事结局", (total*2//3+1, total)),
            ]
            return segments
        
        # 标准5段结构
        p1 = total // 10          # 10% 开场
        p2 = total * 3 // 10      # 30% 铺垫
        p3 = total * 5 // 10      # 50% 转折
        p4 = total * 8 // 10      # 80% 高潮
        
        segments = [
            FrameworkSegment(1, "开场钩子", "悬疑", "铺垫", "吸引观众注意", (1, p1)),
            FrameworkSegment(2, "背景铺垫", "平静", "铺垫", "交代人物关系", (p1+1, p2)),
            FrameworkSegment(3, "冲突升级", "紧张", "升级", "矛盾开始激化", (p2+1, p3)),
            FrameworkSegment(4, "高潮爆发", "高潮", "爆发", "剧情最激烈处", (p3+1, p4)),
            FrameworkSegment(5, "悬念收尾", "悬疑", "收尾", "留下悬念", (p4+1, total)),
        ]
        
        return segments
    
    def get_segment_for_scene(
        self, 
        scene_idx: int, 
        framework: List[FrameworkSegment]
    ) -> Optional[FrameworkSegment]:
        """
        获取场景对应的框架段落
        
        参数：
            scene_idx: 场景索引（从1开始）
            framework: 框架列表
        
        返回：对应的框架段落
        """
        for segment in framework:
            start, end = segment.scene_range
            if start <= scene_idx <= end:
                return segment
        
        # 默认返回最后一个
        return framework[-1] if framework else None
    
    def save_framework(self, framework: List[FrameworkSegment], output_path: str):
        """保存框架到文件"""
        data = [seg.to_dict() for seg in framework]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f"[Framework] 框架已保存: {output_path}")
    
    def load_framework(self, input_path: str) -> Optional[List[FrameworkSegment]]:
        """从文件加载框架"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            segments = []
            for item in data:
                segment = FrameworkSegment(
                    segment_id=item.get('segment_id', 0),
                    theme=item.get('theme', ''),
                    emotion=item.get('emotion', ''),
                    narrative_goal=item.get('narrative_goal', ''),
                    key_point=item.get('key_point', ''),
                    scene_range=tuple(item.get('scene_range', [1, 1]))
                )
                segments.append(segment)
            
            log(f"[Framework] 框架已加载: {len(segments)}个段落")
            return segments
        except Exception as e:
            log(f"[Framework] 加载失败: {e}")
            return None


# 测试
if __name__ == "__main__":
    generator = StoryFrameworkGenerator()
    
    # 测试场景
    test_scenes = [
        {'dialogue': '你是谁？', 'emotion': 'angry', 'importance': 0.9},
        {'dialogue': '我有话要告诉你', 'emotion': 'neutral', 'importance': 0.5},
        {'dialogue': '', 'emotion': 'neutral', 'importance': 0.2},
    ] * 20  # 60个场景
    
    framework = generator.generate_framework(
        title="测试剧",
        media_type="tv",
        episode=1,
        plot_summary="这是一个测试剧情",
        scenes=test_scenes
    )
    
    print("\n生成的框架:")
    for seg in framework:
        print(f"  [{seg.segment_id}] {seg.theme} | {seg.emotion} | {seg.narrative_goal}")
        print(f"      关键点: {seg.key_point}")
        print(f"      场景: {seg.scene_range[0]}-{seg.scene_range[1]}")

