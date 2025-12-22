# core/script_generator.py - 解说剧本生成器
"""
SmartVideoClipper v3.0 - 解说剧本生成器

核心理念：解说驱动剪辑

工作流程：
1. 接收剧情理解结果
2. 规划解说结构（开场白 → 故事展开 → 高潮 → 结局）
3. 生成分段解说，每段带有：
   - 解说文本
   - 对应的画面描述（用于后续匹配素材）
   - 时间戳范围
   - 是否保留原声

输出：可直接用于剪辑的解说剧本
"""

import ollama
import re
from typing import Dict, List, Optional


def get_available_model() -> str:
    """获取可用的 Ollama 模型"""
    preferred = ['qwen3:30b', 'qwen3:8b', 'qwen2.5:7b', 'gemma3:4b', 'gemma2', 'llama3', 'codellama']
    
    try:
        models_response = ollama.list()
        available = []
        
        # 兼容不同版本的 ollama 返回格式
        if isinstance(models_response, dict) and 'models' in models_response:
            # 老版本格式: {'models': [{'name': 'qwen3:8b', ...}]}
            for m in models_response['models']:
                name = m.get('name', '') if isinstance(m, dict) else str(m)
                if name:
                    available.append(name)
        elif hasattr(models_response, 'models'):
            # 新版本格式: ListResponse 对象
            for m in models_response.models:
                name = getattr(m, 'name', '') or getattr(m, 'model', '')
                if name:
                    available.append(name)
        
        print(f"[AI] 已安装模型: {available}")
        
        # 按优先级匹配
        for pref in preferred:
            pref_base = pref.split(':')[0].lower()
            for avail in available:
                avail_base = avail.split(':')[0].lower()
                if pref_base == avail_base or pref_base in avail.lower():
                    print(f"[AI] 选择模型: {avail}")
                    return avail
        
        # 返回第一个可用模型
        if available:
            print(f"[AI] 使用第一个可用模型: {available[0]}")
            return available[0]
            
    except Exception as e:
        print(f"[WARNING] 模型检测失败: {e}")
    
    # 默认返回，调用时会失败并触发 fallback
    print("[WARNING] 未找到可用模型，将使用备用剧本")
    return None


class ScriptGenerator:
    """
    解说剧本生成器
    
    输入：剧情理解结果
    输出：分段解说剧本
    """
    
    def __init__(self):
        self.model = get_available_model()
    
    def generate(
        self,
        story_understanding: Dict,
        target_duration: int = 300,
        style: str = "幽默"
    ) -> List[Dict]:
        """
        生成解说剧本
        
        参数：
            story_understanding: 剧情理解结果
            target_duration: 目标解说时长（秒）
            style: 解说风格
        
        返回：
        [
            {
                'segment_id': 1,
                'narration_text': '今天给大家讲一个...',
                'scene_description': '男主角站在街头',
                'source_time_range': [100, 120],  # 原视频时间范围
                'duration': 20,  # 这段解说大约多长
                'keep_original_audio': False,  # 是否保留原声
                'emotion': 'neutral',  # 这段的情感基调
            },
            ...
        ]
        """
        print("\n" + "="*60)
        print("📝 解说剧本生成器 v3.0")
        print(f"   风格: {style}")
        print(f"   目标时长: {target_duration}秒")
        print("="*60)
        
        # 1. 规划剧本结构
        print("\n[1/3] 规划剧本结构...")
        structure = self._plan_structure(story_understanding, target_duration)
        print(f"   ✓ 规划了 {len(structure)} 个段落")
        
        # 2. 生成每段解说
        print("\n[2/3] 生成解说文本...")
        script_segments = self._generate_segments(
            story_understanding, 
            structure, 
            style,
            target_duration
        )
        print(f"   ✓ 生成了 {len(script_segments)} 段解说")
        
        # 3. 匹配素材时间戳
        print("\n[3/3] 匹配视频素材...")
        final_script = self._match_source_material(
            script_segments,
            story_understanding
        )
        print(f"   ✓ 完成素材匹配")
        
        # 统计
        total_narration_chars = sum(len(s.get('narration_text', '')) for s in final_script)
        keep_original_count = sum(1 for s in final_script if s.get('keep_original_audio'))
        
        print("\n" + "="*60)
        print(f"✅ 剧本生成完成！")
        print(f"   总字数: {total_narration_chars} 字")
        print(f"   段落数: {len(final_script)}")
        print(f"   保留原声: {keep_original_count} 段")
        print("="*60)
        
        return final_script
    
    def _plan_structure(
        self, 
        story: Dict, 
        target_duration: int
    ) -> List[Dict]:
        """规划剧本结构"""
        
        # 基础结构
        structure = [
            {
                'phase': 'opening',
                'name': '开场白',
                'duration_ratio': 0.08,  # 8%时间
                'content_focus': '引入话题，制造悬念',
            },
            {
                'phase': 'background',
                'name': '背景介绍',
                'duration_ratio': 0.12,
                'content_focus': '介绍人物和背景',
            },
            {
                'phase': 'development_1',
                'name': '故事展开1',
                'duration_ratio': 0.20,
                'content_focus': '第一个冲突点',
            },
            {
                'phase': 'development_2',
                'name': '故事展开2',
                'duration_ratio': 0.20,
                'content_focus': '矛盾升级',
            },
            {
                'phase': 'climax',
                'name': '高潮',
                'duration_ratio': 0.20,
                'content_focus': '最精彩的部分，建议保留原声',
            },
            {
                'phase': 'resolution',
                'name': '结局',
                'duration_ratio': 0.15,
                'content_focus': '真相揭示，结局',
            },
            {
                'phase': 'ending',
                'name': '收尾',
                'duration_ratio': 0.05,
                'content_focus': '总结评价，引导互动',
            },
        ]
        
        # 根据剧情结构调整
        story_structure = story.get('story_structure', {})
        key_scenes = story.get('key_scenes', [])
        
        # 计算每段时长
        for seg in structure:
            seg['target_duration'] = int(target_duration * seg['duration_ratio'])
        
        # 如果有关键场景，分配到对应段落
        for scene in key_scenes:
            scene_time = scene.get('time', 0)
            
            # 找到对应的段落
            for seg in structure:
                phase = seg['phase']
                if phase in story_structure:
                    time_range = story_structure[phase].get('time_range', [0, 0])
                    if time_range[0] <= scene_time <= time_range[1]:
                        if 'key_scenes' not in seg:
                            seg['key_scenes'] = []
                        seg['key_scenes'].append(scene)
                        break
        
        return structure
    
    def _generate_segments(
        self,
        story: Dict,
        structure: List[Dict],
        style: str,
        target_duration: int
    ) -> List[Dict]:
        """使用AI生成每段解说"""
        
        # 准备上下文
        title = story.get('title', '这部作品')
        plot = story.get('plot_summary', '')[:800]
        characters = story.get('characters', [])
        classic_dialogues = story.get('classic_dialogues', [])
        
        char_intro = '\n'.join([f"- {c['name']}: {c.get('description', c.get('role', ''))}" 
                                for c in characters[:5]])
        
        dialogue_samples = '\n'.join([f"「{d['text']}」" 
                                      for d in classic_dialogues[:5]])
        
        # 构建prompt
        style_guide = self._get_style_guide(style)
        
        prompt = f"""你是一位顶级影视解说博主，风格类似"谷阿莫"、"木鱼水心"。
现在需要为《{title}》创作一个{target_duration}秒的解说视频剧本。

## 作品信息
{plot}

## 主要人物
{char_intro if char_intro else '（暂无详细人物信息）'}

## 经典台词参考
{dialogue_samples if dialogue_samples else '（暂无）'}

## 解说风格要求
{style_guide}

## 剧本结构要求
请按以下结构创作，每段用【段落名】标记，并注明这段应该配什么画面：

1. 【开场白】（约20秒）- 用一个吸引人的问题或悬念开场
2. 【背景介绍】（约30秒）- 简单介绍背景和人物
3. 【故事展开1】（约60秒）- 讲述第一个重要情节
4. 【故事展开2】（约60秒）- 冲突升级
5. 【高潮】（约60秒）- 最精彩的部分，注明【保留原声】的地方
6. 【结局】（约45秒）- 真相和结局
7. 【收尾】（约15秒）- 简短评价，引导点赞关注

## 格式要求
每段格式如下：
【段落名】
[画面：描述这段应该配什么画面]
解说文本...
（如果某处应保留原声，写：【保留原声：描述场景】）

## 禁止内容
- 不要出现"吐槽"、"笑"、"评分多少分"等字眼
- 不要有任何评分数字
- 不要说"接下来让我们看看"这种生硬过渡

请直接开始创作：
"""

        # 如果没有可用模型，直接使用备用剧本
        if not self.model:
            print("   [INFO] 无可用AI模型，使用备用剧本")
            return self._generate_fallback_script(story, structure)

        try:
            print(f"   调用 {self.model} 生成剧本...")
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.7, 'num_predict': 2000}
            )
            
            script_text = response['message']['content']
            
            # 解析生成的剧本
            segments = self._parse_script(script_text, structure)
            
            # 如果解析失败，使用备用剧本
            if not segments or len(segments) < 2:
                print("   [WARNING] AI剧本解析结果不足，补充备用剧本")
                return self._generate_fallback_script(story, structure)
            
            return segments
            
        except Exception as e:
            print(f"   [ERROR] AI生成失败: {e}")
            # 返回简单的备用剧本
            return self._generate_fallback_script(story, structure)
    
    def _get_style_guide(self, style: str) -> str:
        """获取风格指南"""
        guides = {
            '幽默': """
- 语言轻松有趣，偶尔调侃但不刻意
- 用生动的比喻和形象的描述
- 节奏明快，不拖沓
- 可以用一些网络流行语，但不要太多
- 像和朋友聊天一样自然
""",
            '正经解说': """
- 客观专业的叙述风格
- 注重剧情分析和人物解读
- 语言严谨但不枯燥
- 适当加入背景知识
""",
            '悬疑紧张': """
- 营造紧张悬疑的氛围
- 多用设问和悬念
- 节奏时快时慢
- 在关键处戛然而止
""",
            '温情感人': """
- 温暖细腻的叙述
- 注重情感描写
- 语速适中，给观众思考空间
- 在感人处适当停顿
"""
        }
        return guides.get(style, guides['幽默'])
    
    def _parse_script(self, script_text: str, structure: List[Dict]) -> List[Dict]:
        """解析AI生成的剧本"""
        segments = []
        
        # 用段落标记分割
        pattern = r'【([^】]+)】'
        parts = re.split(pattern, script_text)
        
        current_segment = None
        segment_id = 0
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # 检查是否是段落标题
            is_title = any(s['name'] in part or s['phase'] in part.lower() 
                          for s in structure)
            
            if is_title and i + 1 < len(parts):
                segment_id += 1
                current_segment = {
                    'segment_id': segment_id,
                    'phase': part,
                    'narration_text': '',
                    'scene_description': '',
                    'keep_original_audio': False,
                    'original_audio_scenes': []
                }
            elif current_segment is not None:
                # 这是内容部分
                content = part
                
                # 提取画面描述
                scene_match = re.search(r'\[画面[：:]\s*([^\]]+)\]', content)
                if scene_match:
                    current_segment['scene_description'] = scene_match.group(1)
                    content = re.sub(r'\[画面[：:][^\]]+\]', '', content)
                
                # 提取保留原声标记
                original_matches = re.findall(r'【保留原声[：:]\s*([^】]+)】', content)
                if original_matches:
                    current_segment['keep_original_audio'] = True
                    current_segment['original_audio_scenes'] = original_matches
                    content = re.sub(r'【保留原声[：:][^】]+】', '[此处保留原声]', content)
                
                # 清理解说文本
                content = re.sub(r'\s+', ' ', content).strip()
                current_segment['narration_text'] = content
                
                # 估算时长（中文约3-4字/秒）
                char_count = len(re.sub(r'[^\u4e00-\u9fff]', '', content))
                current_segment['duration'] = max(10, char_count // 3)
                
                segments.append(current_segment)
                current_segment = None
        
        return segments
    
    def _generate_fallback_script(
        self, 
        story: Dict, 
        structure: List[Dict]
    ) -> List[Dict]:
        """生成备用剧本（当AI失败时）"""
        
        title = story.get('title', '这部作品')
        plot = story.get('plot_summary', '')[:500]
        
        fallback_segments = [
            {
                'segment_id': 1,
                'phase': '开场白',
                'narration_text': f'今天要给大家介绍的是《{title}》，这是一部非常精彩的作品。',
                'scene_description': '片头画面',
                'duration': 15,
                'keep_original_audio': False,
            },
            {
                'segment_id': 2,
                'phase': '背景介绍',
                'narration_text': plot if plot else f'《{title}》讲述了一个引人入胜的故事。',
                'scene_description': '主角出场',
                'duration': 60,
                'keep_original_audio': False,
            },
            {
                'segment_id': 3,
                'phase': '高潮',
                'narration_text': '接下来是最精彩的部分，让我们来看看。',
                'scene_description': '高潮场景',
                'duration': 60,
                'keep_original_audio': True,
            },
            {
                'segment_id': 4,
                'phase': '收尾',
                'narration_text': '以上就是今天的分享，喜欢的话别忘了点赞关注哦！',
                'scene_description': '结局画面',
                'duration': 15,
                'keep_original_audio': False,
            },
        ]
        
        return fallback_segments
    
    def _match_source_material(
        self,
        script_segments: List[Dict],
        story: Dict
    ) -> List[Dict]:
        """为每段解说匹配原视频素材"""
        
        story_structure = story.get('story_structure', {})
        key_scenes = story.get('key_scenes', [])
        emotional_beats = story.get('emotional_beats', [])
        
        # 获取总时长（从story_structure推断）
        total_duration = 0
        for phase, info in story_structure.items():
            time_range = info.get('time_range', [0, 0])
            total_duration = max(total_duration, time_range[1])
        
        if total_duration == 0:
            total_duration = 2400  # 默认40分钟
        
        # 为每段分配时间范围
        for i, seg in enumerate(script_segments):
            phase = seg.get('phase', '').lower()
            
            # 尝试从story_structure匹配
            matched = False
            for struct_phase, info in story_structure.items():
                if struct_phase in phase or phase in struct_phase:
                    seg['source_time_range'] = info.get('time_range', [0, 60])
                    matched = True
                    break
            
            if not matched:
                # 按顺序均分
                ratio = i / max(len(script_segments), 1)
                start = int(total_duration * ratio)
                end = int(total_duration * (ratio + 0.15))
                seg['source_time_range'] = [start, min(end, total_duration)]
            
            # 标记情感
            seg_start, seg_end = seg['source_time_range']
            for beat in emotional_beats:
                if seg_start <= beat['time'] <= seg_end:
                    seg['emotion'] = beat['emotion']
                    break
            else:
                seg['emotion'] = 'neutral'
        
        return script_segments


# 测试
if __name__ == "__main__":
    generator = ScriptGenerator()
    
    # 模拟剧情理解结果
    test_story = {
        'title': '狂飙',
        'plot_summary': '讲述了一个鱼贩如何一步步成为黑帮老大的故事...',
        'characters': [
            {'name': '高启强', 'role': '主角', 'description': '从鱼贩到黑帮老大'},
            {'name': '安欣', 'role': '配角', 'description': '正义的警察'},
        ],
        'story_structure': {
            'opening': {'time_range': [0, 180], 'description': '人物出场'},
            'development': {'time_range': [180, 1200], 'description': '冲突展开'},
            'climax': {'time_range': [1200, 2000], 'description': '高潮'},
            'resolution': {'time_range': [2000, 2400], 'description': '结局'},
        },
        'classic_dialogues': [
            {'time': 600, 'text': '你知道我是谁吗？'},
        ],
        'emotional_beats': [
            {'time': 800, 'emotion': '紧张', 'intensity': 0.8},
        ],
    }
    
    script = generator.generate(
        story_understanding=test_story,
        target_duration=300,
        style="幽默"
    )
    
    for seg in script:
        print(f"\n--- {seg['phase']} ---")
        print(f"时间范围: {seg['source_time_range']}")
        print(f"解说: {seg['narration_text'][:100]}...")

