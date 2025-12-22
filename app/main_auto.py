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
from smart_cut import extract_clips, concat_clips, select_best_clips
from tts_synthesis import TTSEngine
from compose_video import compose_final_video, convert_to_douyin
from movie_info import MovieInfoFetcher


# 处理步骤定义
PROCESS_STEPS = [
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


async def full_auto_process(
    input_video: str,
    movie_name: str = None,
    output_name: str = "抖音解说",
    style: str = "幽默吐槽",
    use_internet: bool = True,
    target_duration: int = 240,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None
):
    """
    全自动处理 - 无需任何人工干预
    """
    
    def report_progress(step: int, detail: str = ""):
        """报告进度"""
        if progress_callback:
            step_info = PROCESS_STEPS[step - 1]
            progress_callback(step, TOTAL_STEPS, step_info[1], detail or step_info[2])
        print(f"\n[Step {step}/{TOTAL_STEPS}] {PROCESS_STEPS[step-1][1]}...")
    
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
    
    # ========== Step 1: 镜头切分 ==========
    report_progress(1, "正在分析视频镜头...")
    scenes, _ = detect_scenes(input_video, str(work_dir))
    
    if not scenes or len(scenes) == 0:
        raise RuntimeError("[ERROR] 镜头检测失败，未检测到任何镜头")
    print(f"   检测到 {len(scenes)} 个镜头")
    GPUManager.clear()
    
    # ========== Step 2: 语音识别 ==========
    report_progress(2, "正在识别视频对白...")
    try:
        segments, transcript = transcribe_video(
            input_video,
            str(work_dir / "subtitles.srt")
        )
        print(f"   识别到 {len(segments)} 段对白")
    except Exception as e:
        print(f"[WARNING] 语音识别失败: {e}")
        segments, transcript = [], ""
    GPUManager.clear()
    
    # ========== Step 3: CLIP画面分析 ==========
    report_progress(3, "正在分析画面内容...")
    analyzer = CLIPAnalyzer()
    analyzed_scenes = analyzer.analyze_video_scenes(input_video, scenes)
    del analyzer
    
    if not analyzed_scenes or len(analyzed_scenes) == 0:
        print("   [WARNING] 画面分析无结果，使用原始镜头列表")
        analyzed_scenes = [{'start': s[0], 'end': s[1], 'is_important': True, 'confidence': 0.5} for s in scenes]
    GPUManager.clear()
    
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
    script = generate_narration_script_enhanced(
        transcript,
        analyzed_scenes,
        movie_name=movie_name,
        style=style,
        use_internet=use_internet
    )
    
    script_file = work_dir / "解说文案.txt"
    script_file.write_text(script, encoding='utf-8')
    print(f"   文案已保存: {script_file}")
    GPUManager.clear()
    
    # ========== Step 6: 自动检测保留原声片段 ==========
    report_progress(6, "正在检测保留原声片段...")
    keep_original = auto_detect_keep_original(segments, analyzed_scenes)
    print(f"   检测到 {len(keep_original)} 个保留原声片段")
    
    # ========== Step 7: 智能剪辑 ==========
    report_progress(7, "正在选取精彩片段并剪辑...")
    
    # 选取重要镜头
    important_scenes = [s for s in analyzed_scenes if s.get('is_important', False)]
    if len(important_scenes) == 0:
        print("   [INFO] 未检测到重要镜头，使用所有镜头")
        important_scenes = analyzed_scenes
    
    # 选取最佳片段
    selected_clips = select_best_clips(important_scenes, target_duration)
    
    if len(selected_clips) == 0:
        print("   [INFO] 片段选取为空，使用前10个镜头")
        selected_clips = []
        for s in analyzed_scenes[:10]:
            if 'start' in s and 'end' in s:
                selected_clips.append({'start': s['start'], 'end': s['end']})
    
    if len(selected_clips) == 0:
        raise RuntimeError("[ERROR] 无法选取任何有效片段")
    
    # 提取片段
    clip_dir = work_dir / "clips"
    try:
        generated_clips = extract_clips(input_video, selected_clips, str(clip_dir))
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
    
    # 视频合成
    composed_video = work_dir / "成品_横屏.mp4"
    try:
        compose_final_video(
            str(edited_video),
            str(narration_file),
            str(composed_video),
            keep_original_segments=keep_original,
            subtitle_path=str(work_dir / "subtitles.srt") if (work_dir / "subtitles.srt").exists() else None,
            mode="mix"
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
            style="幽默吐槽",
            use_internet=True if movie_name else False
        ))
    else:
        print(f"[WARNING] 视频文件不存在: {test_video}")
        print("\n使用方法:")
        print("  python app/main_auto.py 视频文件.mp4")
        print("  python app/main_auto.py 视频文件.mp4 电影名称")
