# core/generate_script.py - AI文案生成
"""
SmartVideoClipper - AI文案生成模块

功能: 使用Ollama+Qwen生成影视解说文案
用途: 根据对白和镜头分析，生成专业的解说文案

依赖: ollama (需要先安装Ollama应用并下载qwen3模型)

支持的模型（按推荐顺序）:
- qwen3:30b (推荐，效果最好)
- qwen3:8b
- qwen2.5:7b
"""

import ollama
import re


def get_available_model():
    """
    自动检测并选择最佳可用模型
    优先级: qwen3 > qwen2.5 > gemma3 > codellama
    """
    preferred_models = [
        'qwen3:30b',
        'qwen3:8b', 
        'qwen2.5:7b',
        'qwen2.5:3b',
        'qwen:7b',
        'qwen:latest',
        'gemma3:4b',
        'gemma3:latest',
        'codellama',
    ]
    
    try:
        response = ollama.list()
        installed = []
        
        if hasattr(response, 'models'):
            for m in response.models:
                model_name = m.model if hasattr(m, 'model') else str(m)
                installed.append(model_name)
        elif isinstance(response, dict) and 'models' in response:
            for m in response['models']:
                model_name = m.get('name', m.get('model', str(m)))
                installed.append(model_name)
        
        print(f"[AI] 已安装模型: {installed}")
        
        for model in preferred_models:
            for installed_model in installed:
                if model in installed_model or model.split(':')[0] in installed_model:
                    print(f"[AI] 选择模型: {installed_model}")
                    return installed_model
        
        for installed_model in installed:
            if 'qwen' in installed_model.lower():
                print(f"[AI] 使用模型: {installed_model}")
                return installed_model
        
        if installed:
            print(f"[AI] 未找到qwen模型，使用: {installed[0]}")
            return installed[0]
                
    except Exception as e:
        print(f"[WARNING] 模型检测失败: {e}")
    
    return 'qwen3:8b'


# 全局模型变量
OLLAMA_MODEL = None


def clean_script(script: str) -> str:
    """
    清理AI生成的文案，移除不应该出现的内容
    """
    # 移除各种标注和元信息
    patterns_to_remove = [
        r'（[笑吐槽评论旁白音乐背景].*?）',  # 移除（笑）（吐槽）等
        r'\([笑吐槽评论旁白音乐背景].*?\)',   # 移除(笑)(吐槽)等
        r'【[解说文案背景音乐标题].*?】',      # 移除【解说文案】【背景音乐】等元标注
        r'\*\*.*?\*\*',                        # 移除**粗体标记**
        r'---+',                               # 移除分割线
        r'^\s*>\s*',                           # 移除引用符号
        r'【原声[:：]\d+[秒sS]?[-~到]\d+[秒sS]?】',  # 移除原声标记
        r'【保留原声[:：].*?】',               # 移除保留原声标记
        r'人声[:：]?\s*\d+\.?\d*\s*分',       # 移除"人声X分"
        r'配乐[:：]?\s*\d+\.?\d*\s*分',       # 移除"配乐X分"
        r'画面[:：]?\s*\d+\.?\d*\s*分',       # 移除"画面X分"
        r'总分[:：]?\s*\d+\.?\d*\s*分',       # 移除"总分X分"
        r'评分[:：]?\s*\d+\.?\d*',            # 移除评分
    ]
    
    cleaned = script
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE)
    
    # 移除多余的空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # 移除开头结尾的空白
    cleaned = cleaned.strip()
    
    return cleaned


def generate_narration_script(
    transcript: str,
    scene_analysis: list,
    style: str = "专业解说"
) -> str:
    """
    生成影视解说文案（基础版）
    """
    
    important_scenes = [s for s in scene_analysis if s.get('is_important', False)]
    scene_summary = "\n".join([
        f"- {s['start']:.0f}秒: {s.get('scene_type', '未知场景')}"
        for s in important_scenes[:20]
    ])
    
    # 根据风格选择提示词
    style_guide = {
        "专业解说": "客观冷静，像纪录片解说，注重剧情分析和人物刻画",
        "幽默": "轻松诙谐，语言生动有趣，偶尔调侃但不刻意，让观众会心一笑",
        "幽默轻松": "轻松诙谐，语言生动有趣，偶尔调侃但不刻意，让观众会心一笑",
        "悬疑紧张": "营造悬疑氛围，语气紧凑有力，层层制造悬念",
        "温情感人": "温暖细腻，注重情感表达，引发观众共鸣"
    }
    
    style_desc = style_guide.get(style, style_guide["幽默"])
    
    prompt = f"""你是一位专业的影视解说文案作者。请根据以下信息，撰写一段解说文案。

【剧情对白】
{transcript[:4000]}

【场景信息】
{scene_summary if scene_summary else "暂无场景分析"}

【写作要求】
1. 风格：{style_desc}
2. 用第三人称讲述故事（他/她/男主/女主）
3. 字数：800-1200字，适合3-5分钟朗读
4. 语言流畅自然，适合配音朗读
5. 按剧情发展顺序叙述，保持故事连贯

【重要禁止事项】
- 禁止出现任何标注如（笑）（吐槽）（旁白）
- 禁止出现评分如"人声X分""总分X分"
- 禁止出现【原声】【背景音乐】等技术标记
- 禁止出现时间戳如"00:15-00:25"
- 禁止使用markdown格式如**粗体**或---分割线
- 直接输出纯文字解说内容

【输出】
直接开始解说，不要任何前言："""
    
    global OLLAMA_MODEL
    if OLLAMA_MODEL is None:
        OLLAMA_MODEL = get_available_model()
    
    print(f"[AI] 使用 {OLLAMA_MODEL} 生成解说文案...")
    print("   （大约需要30-90秒）")
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.6,  # 降低随机性，输出更稳定
                'top_p': 0.85,
                'num_predict': 2000
            }
        )
        
        script = response['message']['content']
        
        # 清理文案
        script = clean_script(script)
        
        print(f"[OK] 文案生成完成，共 {len(script)} 字")
        
        return script
    except Exception as e:
        print(f"[ERROR] Ollama调用失败: {e}")
        print(f"[TIP] 请确保：1) Ollama已安装并运行 2) 已下载模型")
        return ""


def generate_narration_script_enhanced(
    transcript: str,
    scene_analysis: list,
    movie_name: str = None,
    style: str = "专业解说",
    use_internet: bool = True
) -> str:
    """
    增强版文案生成（支持联网获取电影信息）
    """
    
    # 联网获取电影信息
    movie_context = ""
    if use_internet and movie_name:
        try:
            from .movie_info import MovieInfoFetcher
            fetcher = MovieInfoFetcher()
            info = fetcher.search_movie(movie_name)
            
            movie_context = f"""
【影片信息】
- 片名：{info.get('title', movie_name)}
- 类型：{', '.join(info.get('genres', ['未知']))}
- 导演：{info.get('director', '未知')}
- 主演：{', '.join(info.get('cast', [])[:3]) if info.get('cast') else '未知'}
- 简介：{info.get('overview', '')[:200]}
"""
            print(f"[NET] 已获取影片信息: {info.get('title')}")
        except Exception as e:
            print(f"[WARNING] 联网搜索失败: {e}")
    
    # 整理场景信息
    important_scenes = [s for s in scene_analysis if s.get('is_important', False)]
    if not important_scenes:
        important_scenes = scene_analysis[:20]  # 没有重要标记则取前20个
    
    scene_summary = "\n".join([
        f"- {s['start']:.0f}秒: {s.get('scene_type', '场景')}"
        for s in important_scenes[:15]
    ])
    
    # 风格指南
    style_guide = {
        "专业解说": "客观冷静，像纪录片解说，深入分析剧情和人物动机",
        "幽默": "语言轻松有趣，讲述时自然幽默，不刻意搞笑，让人看得舒服",
        "幽默轻松": "语言轻松有趣，讲述时自然幽默，不刻意搞笑，让人看得舒服",
        "悬疑紧张": "营造悬疑氛围，语气紧凑有力，抓住观众的好奇心",
        "温情感人": "温暖细腻，注重情感表达，让观众产生共鸣"
    }
    
    style_desc = style_guide.get(style, style_guide["幽默"])
    
    prompt = f"""你是一位资深的影视解说文案作者，作品风格类似"木鱼水心"。

{movie_context}

【本集对白节选】
{transcript[:5000]}

【关键场景】
{scene_summary if scene_summary else "（场景信息缺失，请根据对白推断剧情）"}

【创作要求】
1. 写作风格：{style_desc}
2. 叙述视角：第三人称（他/她/男主/女主/角色名）
3. 篇幅：1000-1500字，约4-6分钟朗读时长
4. 结构：开篇引入 → 剧情发展 → 高潮转折 → 结尾留悬念
5. 语言：流畅自然，有节奏感，适合配音朗读

【严格禁止】
× 任何括号标注：（笑）（吐槽）（旁白）（配乐）
× 任何评分内容：人声X分、画面X分、总分
× 任何时间标记：【原声:XX秒】、00:15-00:25
× 任何格式符号：**粗体**、---分割线、> 引用
× 任何元描述：背景音乐渐入、画面切换等

【开始创作】
直接从故事内容开始，第一句就进入剧情："""
    
    global OLLAMA_MODEL
    if OLLAMA_MODEL is None:
        OLLAMA_MODEL = get_available_model()
    
    print(f"[AI] 使用 {OLLAMA_MODEL} 生成增强版解说文案...")
    print("   （大约需要60-120秒）")
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.6,
                'top_p': 0.85,
                'num_predict': 2500
            }
        )
        
        script = response['message']['content']
        
        # 清理文案
        script = clean_script(script)
        
        print(f"[OK] 增强版文案生成完成，共 {len(script)} 字")
        
        return script
    except Exception as e:
        print(f"[ERROR] Ollama调用失败: {e}")
        print(f"[TIP] 请确保：1) Ollama已安装并运行 2) 已下载模型")
        return ""


# 测试
if __name__ == "__main__":
    print("测试AI文案生成...")
    
    transcript = """
    安欣走进办公室，高启强已经等在那里。
    安欣：你找我？
    高启强：安队长，我们又见面了。
    安欣：有什么事直说。
    高启强：我只是想聊聊，关于京海的未来。
    """
    
    scenes = [
        {'start': 10, 'scene_type': '办公室对话', 'is_important': True},
        {'start': 30, 'scene_type': '紧张对峙', 'is_important': True},
    ]
    
    try:
        script = generate_narration_script(transcript, scenes, "专业解说")
        print("\n生成的文案:")
        print("-" * 50)
        print(script)
    except Exception as e:
        print(f"[ERROR] 生成失败: {e}")
