# core/hook_generator.py - 钩子开场与悬念结尾生成器 v5.6
"""
SmartVideoClipper - 钩子开场与悬念结尾生成器 v5.6

核心功能：
1. 生成吸引人的开场白（钩子）
2. 生成引发期待的悬念结尾
3. 智能判断是否需要添加

设计原则：
- 开场钩子：设悬念、提问、反差，吸引观众
- 悬念结尾：留白、期待、升华，引导继续观看
"""

import sys
import re
from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def log(msg: str):
    """统一日志输出"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================
# 真人解说词库
# ============================================================

# 开场钩子模板
HOOK_TEMPLATES = [
    "你能想象吗？{event}",
    "接下来这{duration}，将颠覆你的认知",
    "这是一个关于{theme}的故事，却没人料到结局会是这样",
    "当{event}发生时，所有人都傻眼了",
    "{character}，从{start}到{end}，只用了{time}",
    "有些人，注定不平凡",
    "命运的齿轮，从这一刻开始转动",
]

# 承上启下词库
TRANSITION_PHRASES = [
    "就在这时",
    "谁也没想到",
    "然而事情并没有那么简单",
    "更让人意外的是",
    "命运的齿轮开始转动",
    "一切的转折点出现了",
    "但这仅仅是开始",
    "风暴即将来临",
]

# 情绪递进词库
EMOTION_ESCALATION = [
    "更可怕的是",
    "更让人心寒的是",
    "这一刻，{character}终于明白了",
    "所有人都屏住了呼吸",
    "空气仿佛凝固了",
    "沉默，是最好的回答",
]

# 悬念结尾模板
SUSPENSE_ENDINGS = [
    "更大的风暴，还在后面",
    "{character}的选择会带来什么后果？",
    "命运的安排，往往出人意料",
    "真相，远比想象的更加残酷",
    "这场博弈，才刚刚开始",
    "下一集，见证{character}的蜕变",
    "故事，远未结束",
]

# 升华结尾模板（用于最后一集或电影）
CONCLUSION_ENDINGS = [
    "有些路，一旦走上去，就再也回不了头",
    "这就是{theme}的故事",
    "人生没有彩排，每一天都是现场直播",
    "选择，决定命运",
    "每个人心中，都有一片不可触碰的领域",
]


class HookGenerator:
    """
    钩子开场与悬念结尾生成器 v5.6
    
    职责：
    1. 生成开场钩子
    2. 生成悬念结尾
    3. 智能判断添加时机
    """
    
    def __init__(self, llm_model: str = None):
        """
        初始化生成器
        
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
    
    def _extract_key_elements(self, plot_summary: str, main_character: str) -> str:
        """
        v5.7：从剧情中提取关键元素用于个性化钩子
        """
        elements = []
        
        if main_character:
            elements.append(f"主角: {main_character}")
        
        if plot_summary:
            # 提取人名
            import re
            names = re.findall(r'([高李王张刘陈安唐龚][^\s，。、]{0,2})', plot_summary)
            if names:
                unique_names = list(set(names))[:3]
                elements.append(f"人物: {', '.join(unique_names)}")
            
            # 提取地点
            places = re.findall(r'(京海|省|市|区|县)', plot_summary)
            if places:
                elements.append(f"地点: {list(set(places))[0]}")
            
            # 提取关键词
            keywords = []
            if '扫黑' in plot_summary or '除恶' in plot_summary:
                keywords.append('扫黑除恶')
            if '涉黑' in plot_summary or '黑帮' in plot_summary:
                keywords.append('涉黑组织')
            if '教育整顿' in plot_summary:
                keywords.append('教育整顿')
            if keywords:
                elements.append(f"关键词: {', '.join(keywords)}")
        
        return ' | '.join(elements) if elements else '(无)'
    
    def should_add_hook(
        self,
        media_type: str,
        episode: int = 1,
        total_episodes: int = 1
    ) -> bool:
        """
        判断是否需要添加开场钩子
        
        规则：
        - 电视剧第一集：必须
        - 电影：必须
        - 电视剧其他集：建议（效果更好）
        """
        # 所有情况都建议添加钩子
        return True
    
    def should_add_suspense(
        self,
        media_type: str,
        episode: int = 1,
        total_episodes: int = 1
    ) -> Tuple[bool, str]:
        """
        判断是否需要添加悬念结尾
        
        返回：(是否添加, 结尾类型 'suspense'悬念/'conclusion'升华)
        """
        if media_type == "movie":
            # 电影：升华结尾
            return True, "conclusion"
        
        if episode < total_episodes:
            # 电视剧非最后一集：悬念结尾
            return True, "suspense"
        else:
            # 电视剧最后一集：升华结尾
            return True, "conclusion"
    
    def generate_hook(
        self,
        title: str,
        plot_summary: str,
        main_character: str = "",
        style: str = "幽默",
        duration_minutes: int = 10
    ) -> str:
        """
        生成开场钩子
        
        参数：
            title: 作品名称
            plot_summary: 剧情概要
            main_character: 主角名称
            style: 解说风格
            duration_minutes: 视频时长（分钟）
        
        返回：开场钩子文本（30-50字）
        """
        log(f"[Hook] 生成开场钩子...")
        
        # 尝试AI生成
        if self.llm_model:
            hook = self._ai_generate_hook(
                title, plot_summary, main_character, style, duration_minutes
            )
            if hook and len(hook) >= 15:
                log(f"[Hook] AI生成成功: {hook[:30]}...")
                return hook
        
        # 备用：模板生成
        hook = self._template_generate_hook(
            title, plot_summary, main_character, duration_minutes
        )
        log(f"[Hook] 模板生成: {hook[:30]}...")
        return hook
    
    def _ai_generate_hook(
        self,
        title: str,
        plot_summary: str,
        main_character: str,
        style: str,
        duration_minutes: int
    ) -> Optional[str]:
        """v5.7.2改进：AI生成个性化开场钩子（增强版）"""
        if not self.llm_model:
            return None
        
        try:
            import ollama
            
            # v5.7.2: 针对《狂飙》等剧的专属开场白
            if '狂飙' in title:
                specific_hint = "高启强从卖鱼到黑帮老大"
            elif '人民的名义' in title:
                specific_hint = "反腐风暴席卷官场"
            else:
                specific_hint = plot_summary[:50] if plot_summary else ""
            
            char = main_character if main_character else "主角"
            
            # v5.7.2: 更明确的prompt
            prompt = f"""/no_think
为《{title}》写一句开场白（25-45字）：

关键：{specific_hint}
主角：{char}

示例格式：
- "一个卖鱼的小贩，如何成为一手遮天的黑老大？"
- "扫黑除恶风暴下，谁在颤抖？"

禁止输出思考过程，直接写开场白："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 150,
                    'temperature': 0.7,
                }
            )
            
            # v5.7.3: 只从content提取，绝不使用thinking
            msg = response.get('message', {})
            result = ""
            
            if hasattr(msg, 'content') and msg.content:
                result = msg.content.strip()
            
            # v5.7.3: content为空返回None，不从thinking提取
            if not result:
                log(f"[Hook] AI返回为空")
                return None
            
            # 清理格式
            result = result.strip('"\'')
            result = re.sub(r'^开场白[：:]\s*', '', result)
            result = re.sub(r'^【.*?】\s*', '', result)
            result = re.sub(r'^-\s*', '', result)
            result = re.sub(r'^["\']', '', result)
            result = re.sub(r'["\']$', '', result)
            
            # v5.7.2: 放宽长度验证（10-100字都接受）
            if len(result) < 10:
                log(f"[Hook] 结果太短: {len(result)}字")
                return None
            if len(result) > 100:
                result = result[:100]  # 截断而不是丢弃
            
            return result
            
        except Exception as e:
            log(f"[Hook] AI生成异常: {e}")
            return None
    
    def _template_generate_hook(
        self,
        title: str,
        plot_summary: str,
        main_character: str,
        duration_minutes: int
    ) -> str:
        """模板生成开场钩子"""
        import random
        
        # 提取关键信息
        if main_character:
            char = main_character
        else:
            # 尝试从剧情中提取人名
            char = "主角"
        
        # 随机选择模板
        templates = [
            f"接下来的{duration_minutes}分钟，带你看完《{title}》",
            f"命运的齿轮，从这一刻开始转动",
            f"有些人，注定不平凡。{char}的故事，从这里开始",
            f"你永远不知道，下一秒会发生什么",
            f"这是一个关于选择的故事",
        ]
        
        return random.choice(templates)
    
    def generate_ending(
        self,
        title: str,
        plot_summary: str,
        ending_type: str = "suspense",
        main_character: str = "",
        style: str = "幽默",
        has_next_episode: bool = True
    ) -> str:
        """
        生成结尾
        
        参数：
            title: 作品名称
            plot_summary: 剧情概要
            ending_type: 结尾类型 ('suspense'悬念 / 'conclusion'升华)
            main_character: 主角名称
            style: 解说风格
            has_next_episode: 是否有下一集
        
        返回：结尾文本（20-40字）
        """
        log(f"[Hook] 生成{ending_type}结尾...")
        
        # 尝试AI生成
        if self.llm_model:
            ending = self._ai_generate_ending(
                title, plot_summary, ending_type, main_character, style, has_next_episode
            )
            if ending and len(ending) >= 10:
                log(f"[Hook] AI生成成功: {ending[:30]}...")
                return ending
        
        # 备用：模板生成
        ending = self._template_generate_ending(ending_type, main_character, has_next_episode)
        log(f"[Hook] 模板生成: {ending[:30]}...")
        return ending
    
    def _ai_generate_ending(
        self,
        title: str,
        plot_summary: str,
        ending_type: str,
        main_character: str,
        style: str,
        has_next_episode: bool
    ) -> Optional[str]:
        """AI生成结尾"""
        if not self.llm_model:
            return None
        
        try:
            import ollama
            
            if ending_type == "suspense":
                type_desc = "悬念结尾，引导观看下一集"
                templates = """
- "更大的风暴，还在后面"
- "xxx的选择会带来什么？"
- "命运的齿轮才刚刚开始转动"
- "故事，远未结束"
- "下一集，见证xxx的蜕变"
"""
            else:
                type_desc = "升华结尾，点评人物命运或升华主题"
                templates = """
- "有些路，一旦走上去，就再也回不了头"
- "选择，决定命运"
- "这就是xxx的故事"
- "人生没有彩排，每一天都是现场直播"
"""
            
            # v5.7.2: 简化prompt，禁止思考
            prompt = f"""/no_think
为《{title}》生成结尾（20-40字）：

剧情：{plot_summary[:100] if plot_summary else ''}
类型：{type_desc}
风格：{style}

禁止输出思考过程，直接输出结尾："""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_predict': 150,
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
            result = re.sub(r'^结尾[：:]\s*', '', result)
            
            # 验证长度
            if len(result) < 10 or len(result) > 80:
                return None
            
            return result
            
        except Exception as e:
            log(f"[Hook] AI生成异常: {e}")
            return None
    
    def _template_generate_ending(
        self,
        ending_type: str,
        main_character: str,
        has_next_episode: bool
    ) -> str:
        """模板生成结尾"""
        import random
        
        char = main_character if main_character else "他"
        
        if ending_type == "suspense" and has_next_episode:
            templates = [
                "更大的风暴，还在后面",
                f"{char}的选择会带来什么？下一集揭晓",
                "命运的齿轮才刚刚开始转动",
                "这场博弈，才刚刚开始",
                "故事，远未结束",
            ]
        else:
            templates = [
                "有些路，一旦走上去，就再也回不了头",
                "选择，决定命运",
                "人生没有彩排，每一天都是现场直播",
                "每个人心中，都有一片不可触碰的领域",
            ]
        
        return random.choice(templates)
    
    def get_transition_phrase(self) -> str:
        """获取随机承上启下词"""
        import random
        return random.choice(TRANSITION_PHRASES)
    
    def get_emotion_phrase(self, character: str = "") -> str:
        """获取随机情绪递进词"""
        import random
        phrase = random.choice(EMOTION_ESCALATION)
        return phrase.format(character=character if character else "他")


# 测试
if __name__ == "__main__":
    generator = HookGenerator()
    
    # 测试开场钩子
    hook = generator.generate_hook(
        title="狂飙",
        plot_summary="高启强从鱼贩逆袭成为黑帮老大的故事",
        main_character="高启强",
        style="幽默",
        duration_minutes=15
    )
    print(f"\n开场钩子: {hook}")
    
    # 测试悬念结尾
    ending = generator.generate_ending(
        title="狂飙",
        plot_summary="高启强面临重大抉择",
        ending_type="suspense",
        main_character="高启强",
        has_next_episode=True
    )
    print(f"悬念结尾: {ending}")
    
    # 测试升华结尾
    ending2 = generator.generate_ending(
        title="狂飙",
        plot_summary="高启强的结局",
        ending_type="conclusion",
        main_character="高启强",
        has_next_episode=False
    )
    print(f"升华结尾: {ending2}")
    
    # 测试承上启下词
    print(f"\n承上启下词: {generator.get_transition_phrase()}")
    print(f"情绪递进词: {generator.get_emotion_phrase('高启强')}")

