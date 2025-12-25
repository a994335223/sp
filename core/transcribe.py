# core/transcribe.py - 语音识别
"""
SmartVideoClipper - 语音识别模块

功能: 使用faster-whisper提取视频中的对白
用途: 生成带精确时间戳的字幕

依赖: faster-whisper, torch
"""

import os
import sys
import json

# 关键：在导入 faster_whisper 之前设置 HuggingFace 镜像
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from faster_whisper import WhisperModel

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.gpu_manager import GPUManager


def _generate_initial_prompt(media_type: str = "movie", title: str = None) -> str:
    """
    生成智能initial_prompt，解决Whisper中文识别乱码问题
    
    原理：
    1. initial_prompt告诉模型期望输出简体中文
    2. 包含常见词汇帮助模型建立上下文
    3. 根据媒体类型调整提示内容
    
    参数:
        media_type: "movie" 或 "tv"
        title: 视频标题（可选）
    
    返回:
        优化后的initial_prompt字符串
    """
    # 基础提示 - 引导简体中文输出（全网公认最有效的方案）
    base_prompt = "以下是普通话的句子。"
    
    # 根据媒体类型添加上下文
    if media_type == "tv":
        context = "这是一段中国大陆电视剧的对白内容。"
    else:
        context = "这是一段中国大陆电影的对白内容。"
    
    # 常见中文词汇（帮助模型建立词汇表，减少乱码）
    common_words = "说话、什么、怎么、为什么、知道、可以、不能、现在、时候、事情、问题、工作、调查、发现、证据"
    
    # 如果有标题，提取可能的专有名词
    title_hint = ""
    if title:
        # 清理标题，提取中文部分
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]+', title)
        if chinese_chars:
            title_hint = f"本片名为《{''.join(chinese_chars)}》。"
    
    # 组合完整prompt
    full_prompt = f"{base_prompt}{context}{title_hint}常用词：{common_words}。"
    
    return full_prompt


def transcribe_video(video_path: str, output_srt: str = None, media_type: str = "movie", title: str = None):
    """
    视频语音转文字（自动适配显卡）- 带实时进度
    
    参数:
        video_path: 视频路径
        output_srt: 字幕输出路径（可选）
        media_type: 媒体类型 ("movie" 或 "tv")
        title: 视频标题（可选，用于提升专有名词识别）
    
    返回:
        segments: 带时间戳的字幕列表 [{'start': 0.0, 'end': 2.5, 'text': '...'}, ...]
        full_text: 完整文本字符串
    """
    import time
    from datetime import datetime
    
    def log(msg):
        """带时间戳的日志输出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
    
    log(f"[ASR] ========== 语音识别开始 ==========")
    log(f"[ASR] 输入文件: {video_path}")
    log(f"[ASR] 媒体类型: {media_type}")
    log(f"[ASR] 预计耗时: 10-15分钟（45分钟视频）")
    
    # 自动根据显存选择模型
    log(f"[ASR] 步骤1/4: 检测GPU和加载模型...")
    config = GPUManager.get_optimal_config()
    
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    log(f"[ASR]    设备: {device}")
    log(f"[ASR]    模型: {config['whisper']}")
    log(f"[ASR]    精度: {compute_type}")
    
    log(f"[ASR] 步骤2/4: 加载Whisper模型（可能需要1-2分钟）...")
    start_load = time.time()
    model = WhisperModel(
        config['whisper'],
        device=device,
        compute_type=compute_type
    )
    log(f"[ASR]    模型加载完成，耗时 {time.time()-start_load:.1f}秒")
    
    # 生成智能initial_prompt
    log(f"[ASR] 步骤3/4: 准备识别参数...")
    initial_prompt = _generate_initial_prompt(media_type, title)
    log(f"[ASR]    识别引导: {initial_prompt[:40]}...")
    
    log(f"[ASR] 步骤4/4: 开始识别（这是最耗时的步骤，请耐心等待）...")
    start_transcribe = time.time()
    
    # transcribe返回生成器，实际识别在迭代时进行
    segments_generator, info = model.transcribe(
        video_path,
        language="zh",
        initial_prompt=initial_prompt,
        condition_on_previous_text=False,
        temperature=0,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200
        ),
        beam_size=5,
        best_of=5
    )
    
    log(f"[ASR]    音频时长: {info.duration:.0f}秒 ({info.duration/60:.1f}分钟)")
    log(f"[ASR]    检测语言: {info.language} (置信度: {info.language_probability:.2f})")
    log(f"[ASR]    开始逐段识别...")
    
    # 处理识别结果
    segments = []
    full_text = ""
    
    # v5.7.2: 导入过滤函数
    try:
        from content_filter import filter_sensitive_content, is_ad_content
        use_filter = True
    except ImportError:
        use_filter = False
        def is_ad_content(text):
            return False
    
    seg_count = 0
    ad_count = 0
    last_progress = 0
    for seg in segments_generator:
        seg_count += 1
        
        # 每处理10%显示一次进度
        if info.duration > 0:
            progress = int((seg.end / info.duration) * 100)
            if progress >= last_progress + 10:
                elapsed = time.time() - start_transcribe
                log(f"[ASR]    进度: {progress}% | 已识别: {seg_count}段 | 耗时: {elapsed:.0f}秒")
                last_progress = progress
        elif seg_count % 30 == 0:
            elapsed = time.time() - start_transcribe
            log(f"[ASR]    已处理 {seg_count} 个片段... (耗时: {elapsed:.0f}秒)")
        
        text = seg.text.strip()
        
        # v5.7.2: 首先过滤广告内容
        if is_ad_content(text):
            ad_count += 1
            continue  # 跳过广告段落
        
        if use_filter:
            text, removed = filter_sensitive_content(text)
            if removed:
                log(f"[ASR]    [FILTER] 过滤敏感词: {removed}")
        
        segment = {
            'start': seg.start,
            'end': seg.end,
            'text': text
        }
        segments.append(segment)
        full_text += text
    
    if ad_count > 0:
        log(f"[ASR]    [FILTER] 已过滤 {ad_count} 条广告/乱码")
    
    transcribe_time = time.time() - start_transcribe
    log(f"[ASR] ========== 语音识别完成 ==========")
    log(f"[ASR]    识别片段: {len(segments)} 个")
    log(f"[ASR]    识别耗时: {transcribe_time:.1f}秒 ({transcribe_time/60:.1f}分钟)")
    log(f"[ASR]    文本长度: {len(full_text)} 字符")
    
    # [FIX] 释放模型显存
    del model
    GPUManager.clear()
    
    # 保存SRT字幕
    if output_srt:
        save_srt(segments, output_srt)
    
    return segments, full_text


def save_srt(segments: list, output_path: str):
    """保存SRT字幕文件"""
    
    def format_time(seconds):
        """转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    
    print(f"[OK] 字幕已保存: {output_path}")


def save_json(segments: list, output_path: str):
    """保存JSON格式的识别结果"""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] JSON已保存: {output_path}")


# 使用示例
if __name__ == "__main__":
    # 测试语音识别
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        segments, text = transcribe_video(test_video, "字幕.srt")
        print(f"\n全片对白预览: {text[:500]}...")
        
        # 保存JSON
        save_json(segments, "segments.json")
    else:
        print(f"[WARNING] 测试视频不存在: {test_video}")
        print("请提供一个视频文件进行测试")
