# app/main_auto.py - 全自动处理（无需任何人工干预）推荐使用
"""
SmartVideoClipper - 完整版主程序

功能: 全自动处理视频，支持联网增强、原声保留检测等
特点: 无需任何人工干预，一键完成所有处理

使用方法:
    python app/main_auto.py
"""

import os
import sys

# 关键：在导入任何模型库之前设置 HuggingFace 镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing import Callable, Optional

# 加载环境变量
load_dotenv()

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

# 从 utils/ 导入
from utils.gpu_manager import GPUManager

# 从 core/ 导入
from scene_detect import detect_scenes
from remove_silence import remove_silence
from transcribe import transcribe_video
from analyze_frames import CLIPAnalyzer
from generate_script import generate_narration_script_enhanced
from auto_detect_highlights import auto_detect_keep_original
from smart_cut import extract_clips, concat_clips
from tts_synthesis import TTSEngine
from compose_video import compose_final_video, convert_to_douyin
from movie_info import MovieInfoFetcher
from intro_outro_detect import auto_trim_intro_outro
from smart_importance import calculate_importance_scores, select_important_clips  # 智能重要性评分


# 处理步骤定义（新增Step 0）
PROCESS_STEPS = [
    (0, "预处理", "检测并去除片头片尾"),
    (1, "镜头切分", "使用 PySceneDetect 分析视频镜头"),
    (2, "语音识别", "使用 faster-whisper 识别对白"),
    (3, "画面分析", "使用 CLIP 分析画面内容"),
    (4, "联网搜索", "从豆瓣获取电影信息"),
    (5, "生成文案", "使用 AI 生成解说文案"),
    (6, "检测原声", "自动检测保留原声片段"),
    (7, "智能剪辑", "选取精彩片段并剪辑"),
    (8, "合成视频", "语音合成 + 视频合成"),
    (9, "优化输出", "静音剪除 + 生成封面"),
]

TOTAL_STEPS = len(PROCESS_STEPS)


def verify_file_exists(file_path: str, description: str = "文件"):
    """验证文件存在且非空"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"[ERROR] {description}不存在: {file_path}")
    if path.stat().st_size == 0:
        raise RuntimeError(f"[ERROR] {description}为空: {file_path}")
    return True


def check_ai_script_valid(script: str) -> bool:
    """检查AI生成的文案是否有效（非模板/非失败）"""
    if not script or len(script) < 100:
        return False
    # 检查是否是失败模板
    fail_markers = [
        "自动生成失败",
        "请手动编辑",
        "AI服务不可用",
        "Ollama调用失败"
    ]
    for marker in fail_markers:
        if marker in script:
            return False
    return True


async def full_auto_process(
    input_video: str,
    movie_name: str = None,
    output_name: str = "抖音解说",
    style: str = "幽默",  # 默认幽默风格（轻松有趣，不刻意吐槽）
    use_internet: bool = True,
    target_duration: int = 240,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    skip_intro_outro: bool = False  # 新增：是否跳过片头片尾检测
):
    """
    全自动处理 - 无需任何人工干预
    """
    
    def report_progress(step: int, detail: str = ""):
        """报告进度"""
        if progress_callback:
            step_info = PROCESS_STEPS[step]
            progress_callback(step, TOTAL_STEPS, step_info[1], detail or step_info[2])
        print(f"\n[Step {step}/{TOTAL_STEPS - 1}] {PROCESS_STEPS[step][1]}...")
    
    # 输入验证
    input_path = Path(input_video)
    if not input_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {input_video}")
    if input_path.suffix.lower() not in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']:
        raise ValueError(f"不支持的视频格式: {input_path.suffix}")
    
    work_dir = Path(f"workspace_{output_name}")
    work_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("SmartVideoClipper - 全自动处理模式")
    print("=" * 70)
    print(f"输入视频: {input_video}")
    print(f"电影名称: {movie_name or '未指定'}")
    print(f"解说风格: {style}")
    print(f"联网搜索: {'开启' if use_internet else '关闭'}")
    print(f"目标时长: {target_duration}秒")
    print(f"工作目录: {work_dir}")
    print("=" * 70)
    
    # ========== Step 0: 片头片尾检测与去除 ==========
    report_progress(0, "正在检测片头片尾...")
    
    if skip_intro_outro:
        print("   [SKIP] 跳过片头片尾检测")
        processed_video = input_video
        intro_offset = 0
    else:
        try:
            trimmed_output = str(work_dir / "trimmed_video.mp4")
            processed_video, intro_offset, outro_time = auto_trim_intro_outro(
                input_video, 
                trimmed_output,
                skip_if_short=300  # 5分钟以下视频跳过
            )
            if processed_video != input_video:
                print(f"   已去除片头: {intro_offset:.1f}秒")
        except Exception as e:
            print(f"   [WARNING] 片头片尾检测失败: {e}，使用原视频")
            processed_video = input_video
            intro_offset = 0
    
    # ========== Step 1: 镜头切分 ==========
    report_progress(1, "正在分析视频镜头...")
    scenes, _ = detect_scenes(processed_video, str(work_dir))
    
    if not scenes or len(scenes) == 0:
        raise RuntimeError("[ERROR] 镜头检测失败，未检测到任何镜头")
    print(f"   检测到 {len(scenes)} 个镜头")
    GPUManager.clear()
    
    # ========== Step 2: 语音识别 ==========
    report_progress(2, "正在识别视频对白...")
    try:
        segments, transcript = transcribe_video(
            processed_video,
            str(work_dir / "subtitles.srt")
        )
        print(f"   识别到 {len(segments)} 段对白")
    except Exception as e:
        print(f"[WARNING] 语音识别失败: {e}")
        segments, transcript = [], ""
    GPUManager.clear()
    
    # ========== Step 3: 智能重要性分析 ==========
    report_progress(3, "正在分析画面和音频内容...")
    
    # 3.1 CLIP画面分析
    try:
        analyzer = CLIPAnalyzer()
        analyzed_scenes = analyzer.analyze_video_scenes(processed_video, scenes)
        del analyzer
    except Exception as e:
        print(f"   [WARNING] CLIP分析失败: {e}")
        analyzed_scenes = [{'start': s['start'], 'end': s['end'], 'scene_type': '未知'} for s in scenes]
    
    if not analyzed_scenes:
        analyzed_scenes = [{'start': s['start'], 'end': s['end'], 'scene_type': '未知'} for s in scenes]
    
    GPUManager.clear()
    
    # 3.2 多维度重要性评分（音频能量+对话密度+情感关键词+场景变化）
    try:
        analyzed_scenes = calculate_importance_scores(
            processed_video,
            analyzed_scenes,
            segments,  # 语音识别的对白片段
            str(work_dir)
        )
    except Exception as e:
        print(f"   [WARNING] 重要性评分失败: {e}，使用默认评分")
        for s in analyzed_scenes:
            s['importance'] = 0.5
            s['is_important'] = True
    
    # ========== Step 4: 联网获取电影信息 ==========
    movie_info = None
    if use_internet and movie_name:
        report_progress(4, f"正在搜索 {movie_name} 的信息...")
        try:
            fetcher = MovieInfoFetcher()
            movie_info = fetcher.search_movie(movie_name)
            print(f"   找到: {movie_info.get('title')} - 评分: {movie_info.get('rating')}")
        except Exception as e:
            print(f"[WARNING] 联网搜索失败: {e}")
    else:
        report_progress(4, "跳过联网搜索")
    
    # ========== Step 5: AI生成文案 ==========
    report_progress(5, "AI正在生成解说文案...")
    
    # 尝试生成AI文案
    script = generate_narration_script_enhanced(
        transcript,
        analyzed_scenes,
        movie_name=movie_name,
        style=style,
        use_internet=use_internet
    )
    
    # [FIX] 检查AI文案是否有效
    ai_script_valid = check_ai_script_valid(script)
    
    if not ai_script_valid:
        print("   [WARNING] AI文案生成失败或无效")
        print("   [INFO] 将使用纯解说模式（不混合原声）")
        # 生成一个基于对白的简单文案
        if transcript and len(transcript) > 50:
            script = f"""这是一部精彩的影视作品。

{transcript[:2000]}

以上就是这部作品的精彩片段。"""
        else:
            script = f"""这是一部精彩的{movie_name if movie_name else '影视作品'}。

故事讲述了一段引人入胜的经历，画面精美，情节紧凑。

让我们一起来欣赏这部作品的精彩片段。"""
    
    script_file = work_dir / "解说文案.txt"
    script_file.write_text(script, encoding='utf-8')
    print(f"   文案已保存: {script_file}")
    print(f"   文案长度: {len(script)} 字")
    GPUManager.clear()
    
    # ========== Step 6: 自动检测保留原声片段 ==========
    report_progress(6, "正在检测保留原声片段...")
    
    # [FIX] 如果AI文案失败，不保留原声（全部使用解说）
    if ai_script_valid:
        keep_original = auto_detect_keep_original(segments, analyzed_scenes)
        print(f"   检测到 {len(keep_original)} 个保留原声片段")
    else:
        keep_original = []  # AI失败时，不保留原声
        print("   [INFO] AI文案无效，跳过原声保留检测")
    
    # ========== Step 7: 智能剪辑 ==========
    report_progress(7, "正在基于重要性评分选取精彩片段...")
    
    # 使用智能重要性评分系统选取片段
    selected_clips = select_important_clips(
        analyzed_scenes,
        target_duration,
        min_clip_duration=2.0,   # 最短2秒
        max_clip_duration=30.0  # 最长30秒
    )
    
    if len(selected_clips) == 0:
        print("   [WARNING] 智能选取为空，回退到传统方法")
        # 回退：按时间顺序选取
        selected_clips = []
        total = 0
        for s in analyzed_scenes:
            if total >= target_duration:
                break
            dur = s.get('end', 0) - s.get('start', 0)
            if dur > 1:
                selected_clips.append({'start': s['start'], 'end': s['end']})
                total += dur
    
    if len(selected_clips) == 0:
        raise RuntimeError("[ERROR] 无法选取任何有效片段")
    
    print(f"   选取了 {len(selected_clips)} 个重要片段")
    
    # 提取片段
    clip_dir = work_dir / "clips"
    try:
        generated_clips = extract_clips(processed_video, selected_clips, str(clip_dir))
    except Exception as e:
        raise RuntimeError(f"[ERROR] 片段提取失败: {e}")
    
    # 拼接片段
    clip_files = sorted(clip_dir.glob("*.mp4"))
    if len(clip_files) == 0:
        raise RuntimeError("[ERROR] 没有生成任何视频片段文件")
    
    edited_video = work_dir / "剪辑后.mp4"
    try:
        concat_clips([str(f) for f in clip_files], str(edited_video))
    except Exception as e:
        raise RuntimeError(f"[ERROR] 视频拼接失败: {e}")
    
    # 验证剪辑后的视频
    verify_file_exists(str(edited_video), "剪辑后视频")
    
    # ========== Step 8: 语音合成 + 视频合成 ==========
    report_progress(8, "正在合成语音和视频...")
    
    # 语音合成
    narration_file = work_dir / "narration.wav"
    tts = TTSEngine("edge")
    await tts.synthesize(script, str(narration_file))
    del tts
    GPUManager.clear()
    
    verify_file_exists(str(narration_file), "解说音频")
    
    # [FIX] 根据AI文案是否有效选择合成模式
    if ai_script_valid and len(keep_original) > 0:
        compose_mode = "mix"  # AI成功且有原声保留，使用混合模式
        print("   使用混合模式（解说+原声）")
    else:
        compose_mode = "replace"  # AI失败或无原声保留，完全替换
        print("   使用替换模式（纯解说）")
    
    # 视频合成
    composed_video = work_dir / "成品_横屏.mp4"
    try:
        compose_final_video(
            str(edited_video),
            str(narration_file),
            str(composed_video),
            keep_original_segments=keep_original if compose_mode == "mix" else None,
            subtitle_path=str(work_dir / "subtitles.srt") if (work_dir / "subtitles.srt").exists() else None,
            mode=compose_mode
        )
    except Exception as e:
        raise RuntimeError(f"[ERROR] 视频合成失败: {e}")
    
    verify_file_exists(str(composed_video), "合成后视频")
    
    # 转换抖音格式
    douyin_output = work_dir / "成品_抖音格式.mp4"
    convert_to_douyin(str(composed_video), str(douyin_output))
    verify_file_exists(str(douyin_output), "抖音格式视频")
    
    # ========== Step 9: 静音剪除 ==========
    report_progress(9, "正在优化视频...")
    final_output = work_dir / f"{output_name}.mp4"
    
    try:
        remove_silence(str(douyin_output), str(final_output))
    except Exception as e:
        print(f"[WARNING] 静音剪除失败: {e}，使用原视频")
        import shutil
        shutil.copy(str(douyin_output), str(final_output))
    
    # 生成封面
    try:
        from cover_generator import auto_generate_cover
        auto_generate_cover(str(final_output), str(work_dir / "cover.jpg"))
    except Exception as e:
        print(f"[INFO] 封面生成跳过: {e}")
    
    # ========== 完成 ==========
    print("\n" + "=" * 70)
    print("全自动处理完成！")
    print("=" * 70)
    print(f"最终视频: {final_output}")
    print(f"解说文案: {script_file}")
    if (work_dir / "cover.jpg").exists():
        print(f"视频封面: {work_dir / 'cover.jpg'}")
    print(f"工作目录: {work_dir}")
    if not ai_script_valid:
        print("\n[提示] AI文案生成失败，使用了纯解说模式")
        print("       请确保Ollama服务已启动: ollama serve")
        print("       并下载模型: ollama pull qwen2.5:7b")
    print("=" * 70)
    
    return str(final_output)


# 运行
if __name__ == "__main__":
    test_video = "test_video.mp4"
    movie_name = None
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
    if len(sys.argv) > 2:
        movie_name = sys.argv[2]
    
    if os.path.exists(test_video):
        asyncio.run(full_auto_process(
            test_video,
            movie_name=movie_name,
            output_name="全自动解说",
            style="幽默",
            use_internet=True if movie_name else False
        ))
    else:
        print(f"[WARNING] 视频文件不存在: {test_video}")
        print("\n使用方法:")
        print("  python app/main_auto.py 视频文件.mp4")
        print("  python app/main_auto.py 视频文件.mp4 电影名称")
