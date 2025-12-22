# core/generate_script.py - AI文案生成
"""
SmartVideoClipper - AI文案生成模块

功能: 使用Ollama+Qwen生成影视解说文案
用途: 根据对白和镜头分析，生成幽默吐槽风格的解说

依赖: ollama (需要先安装Ollama应用并下载qwen3模型)

支持的模型（按推荐顺序）:
- qwen3:30b (推荐，效果最好)
- qwen3:8b
- qwen2.5:7b
"""

import ollama


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
        'gemma3:4b',   # Google的Gemma3也很适合文案生成
        'gemma3:latest',
        'codellama',   # 备选
    ]
    
    try:
        # 获取已安装的模型列表
        response = ollama.list()
        installed = []
        
        # 处理新版ollama返回格式
        if hasattr(response, 'models'):
            for m in response.models:
                model_name = m.model if hasattr(m, 'model') else str(m)
                installed.append(model_name)
        elif isinstance(response, dict) and 'models' in response:
            for m in response['models']:
                model_name = m.get('name', m.get('model', str(m)))
                installed.append(model_name)
        
        print(f"[AI] 已安装模型: {installed}")
        
        # 按优先级查找
        for model in preferred_models:
            for installed_model in installed:
                if model in installed_model or model.split(':')[0] in installed_model:
                    print(f"[AI] 选择模型: {installed_model}")
                    return installed_model
        
        # 如果没有找到首选模型，返回第一个qwen模型
        for installed_model in installed:
            if 'qwen' in installed_model.lower():
                print(f"[AI] 使用模型: {installed_model}")
                return installed_model
        
        # 如果还是没有，返回任意可用模型
        if installed:
            print(f"[AI] 未找到qwen模型，使用: {installed[0]}")
            return installed[0]
                
    except Exception as e:
        print(f"[WARNING] 模型检测失败: {e}")
    
    # 默认返回（会尝试下载）
    return 'qwen3:30b'


# 全局模型变量
OLLAMA_MODEL = None


def generate_narration_script(
    transcript: str,
    scene_analysis: list,
    style: str = "幽默吐槽"
) -> str:
    """
    生成影视解说文案（基础版）
    
    参数:
        transcript: 语音识别的完整对白
        scene_analysis: CLIP分析的镜头信息
        style: 解说风格（幽默吐槽/正经解说/悬疑紧张）
    
    返回:
        生成的解说文案
    """
    
    # 整理重要镜头信息
    important_scenes = [s for s in scene_analysis if s.get('is_important', False)]
    scene_summary = "\n".join([
        f"- {s['start']:.0f}秒: {s['scene_type']}"
        for s in important_scenes[:20]  # 最多20个
    ])
    
    prompt = f"""
你是一个专业的影视解说博主，风格类似"谷阿莫"、"木鱼水心"、"刘哔电影"。

现在请根据以下电影/电视剧信息，生成一段{style}风格的解说文案：

【原片对白摘要】
{transcript[:3000]}...

【重要镜头分析】
{scene_summary}

【要求】
1. 解说风格：{style}
2. 用第三人称讲述故事
3. 在合适的地方加入吐槽和幽默评论
4. 保持故事的连贯性和悬念
5. 总时长控制在3-5分钟（约800-1200字）
6. 标注哪些地方适合保留原声（用【保留原声：XX秒-XX秒】标记）
7. 语言口语化，适合朗读

【输出格式】
直接输出解说文案，段落之间空一行。需要保留原声的地方用标记说明。
"""
    
    # 自动选择模型
    global OLLAMA_MODEL
    if OLLAMA_MODEL is None:
        OLLAMA_MODEL = get_available_model()
    
    print(f"[AI] 使用 {OLLAMA_MODEL} 生成解说文案...")
    print("   （大约需要30-90秒，取决于模型大小）")
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.7,
                'top_p': 0.9,
                'num_predict': 2500  # 增加输出长度
            }
        )
        
        script = response['message']['content']
        print(f"[OK] 文案生成完成，共 {len(script)} 字")
        
        return script
    except Exception as e:
        print(f"[ERROR] Ollama调用失败: {e}")
        print(f"[TIP] 请确保：1) Ollama已安装并运行 2) 已下载模型 (ollama pull qwen3:30b)")
        # 返回一个基础文案模板
        return f"""【解说文案 - 自动生成失败，请手动编辑】

这是一部精彩的影视作品。故事开始于...

【提示】由于AI服务不可用，请根据以下对白摘要手动编写解说：
{transcript[:1000]}...

【保留原声：0秒-10秒】
【保留原声：60秒-70秒】
"""


def generate_narration_script_enhanced(
    transcript: str,
    scene_analysis: list,
    movie_name: str = None,  # 电影名称
    style: str = "幽默吐槽",
    use_internet: bool = True  # 是否联网搜索
) -> str:
    """
    增强版文案生成（支持联网获取电影信息）
    
    参数:
        transcript: 语音识别的完整对白
        scene_analysis: CLIP分析的镜头信息
        movie_name: 电影名称（用于联网搜索）
        style: 解说风格
        use_internet: 是否使用联网搜索增强
    
    返回:
        生成的解说文案
    """
    
    # 联网获取电影信息
    movie_info = ""
    if use_internet and movie_name:
        try:
            from .movie_info import MovieInfoFetcher
            fetcher = MovieInfoFetcher()
            info = fetcher.search_movie(movie_name)
            
            movie_info = f"""
【电影背景信息（来自网络搜索）】
- 片名: {info.get('title', movie_name)}
- 评分: {info.get('rating', '未知')}
- 类型: {', '.join(info.get('genres', []))}
- 导演: {info.get('director', '未知')}
- 主演: {', '.join(info.get('cast', [])[:3])}
- 剧情简介: {info.get('overview', '')[:300]}
"""
            print(f"[NET] 已获取电影信息: {info.get('title')}")
        except Exception as e:
            print(f"[WARNING] 联网搜索失败: {e}")
            movie_info = ""
    
    # 整理重要镜头信息
    important_scenes = [s for s in scene_analysis if s.get('is_important', False)]
    scene_summary = "\n".join([
        f"- {s['start']:.0f}秒: {s['scene_type']}"
        for s in important_scenes[:20]
    ])
    
    prompt = f"""
你是一个专业的影视解说博主，风格类似"谷阿莫"、"木鱼水心"、"刘哔电影"。

{movie_info}

【原片对白摘要】
{transcript[:3000]}...

【重要镜头分析】
{scene_summary}

【要求】
1. 解说风格：{style}
2. 用第三人称讲述故事
3. 在合适的地方加入吐槽和幽默评论
4. 总时长控制在3-5分钟（约800-1200字）
5. **自动判断**哪些地方适合保留原声（高潮、经典台词等）
6. 语言口语化，适合朗读

【输出格式】
直接输出解说文案。
在需要保留原声的地方，自动标注【原声:XX秒-XX秒】。
"""
    
    # 自动选择模型
    global OLLAMA_MODEL
    if OLLAMA_MODEL is None:
        OLLAMA_MODEL = get_available_model()
    
    print(f"[AI] 使用 {OLLAMA_MODEL} 生成增强版解说文案...")
    print("   （大约需要30-90秒，取决于模型大小）")
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={
                'temperature': 0.7,
                'top_p': 0.9,
                'num_predict': 2500  # 增加输出长度
            }
        )
        
        script = response['message']['content']
        print(f"[OK] 增强版文案生成完成，共 {len(script)} 字")
        
        return script
    except Exception as e:
        print(f"[ERROR] Ollama调用失败: {e}")
        print(f"[TIP] 请确保：1) Ollama已安装并运行 2) 已下载模型 (ollama pull qwen3:30b)")
        # 返回一个基础文案模板
        return f"""【解说文案 - 自动生成失败，请手动编辑】

这是一部精彩的{movie_name if movie_name else '影视作品'}。故事开始于...

【提示】由于AI服务不可用，请根据以下对白摘要手动编写解说：
{transcript[:1000]}...

【原声:0秒-10秒】
【原声:60秒-70秒】
"""


# 使用示例
if __name__ == "__main__":
    # 测试文案生成
    print("测试AI文案生成...")
    
    # 模拟数据
    transcript = """
    男主角走进房间，看到女主角正在看窗外。
    男：你怎么了？
    女：没什么，只是在想一些事情。
    男：想什么？
    女：想我们的未来。
    """
    
    scenes = [
        {'start': 10, 'scene_type': '两人对话场景', 'is_important': True},
        {'start': 30, 'scene_type': '浪漫爱情场景', 'is_important': True},
    ]
    
    try:
        script = generate_narration_script(transcript, scenes, "幽默吐槽")
        print("\n生成的文案:")
        print("-" * 50)
        print(script)
    except Exception as e:
        print(f"[ERROR] 生成失败: {e}")
        print("请确保Ollama已安装并运行: ollama serve")
        print("并下载模型: ollama pull qwen2.5:7b")
