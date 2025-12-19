# app/main_auto.py - 全自动处理（无需任何人工干预）⭐推荐使用
"""
SmartVideoClipper - 完整版主程序

功能: 全自动处理视频，支持联网增强、原声保留检测等
特点: 无需任何人工干预，一键完成所有处理

使用方法:
    python app/main_auto.py
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 🔧 添加项目路径（确保能找到所有模块）
PROJECT_ROOT = Path(__file__).parent.parent  # smart-video-clipper/
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))  # 核心模块目录

# 从 utils/ 导入
from utils.gpu_manager import GPUManager

# 从 core/ 导入（已添加到路径，直接导入）
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


async def full_auto_process(
    input_video: str,
    movie_name: str = None,           # 电影名称（用于联网搜索）
    output_name: str = "抖音解说",
    style: str = "幽默吐槽",
    use_internet: bool = True,        # 是否联网搜索电影信息
    target_duration: int = 240        # 目标视频时长（秒）
):
    """
    🤖 全自动处理 - 无需任何人工干预
    
    参数:
        input_video: 输入视频路径（2小时电影/50分钟电视剧）
        movie_name: 电影名称（可选，用于联网搜索信息）
        output_name: 输出文件名
        style: 解说风格（幽默吐槽/正经解说/悬疑紧张）
        use_internet: 是否联网搜索电影信息
        target_duration: 目标视频时长（秒），默认240秒=4分钟
    """
    
    # 🔧 输入验证
    input_path = Path(input_video)
    if not input_path.exists():
        raise FileNotFoundError(f"❌ 视频文件不存在: {input_video}")
    if not input_path.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']:
        raise ValueError(f"❌ 不支持的视频格式: {input_path.suffix}")
    
    work_dir = Path(f"workspace_{output_name}")
    work_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("🤖 SmartVideoClipper - 全自动处理模式")
    print("=" * 70)
    print(f"📹 输入视频: {input_video}")
    print(f"🎬 电影名称: {movie_name or '未指定'}")
    print(f"🎭 解说风格: {style}")
    print(f"🌐 联网搜索: {'开启' if use_internet else '关闭'}")
    print(f"⏱️ 目标时长: {target_duration}秒")
    print("=" * 70)
    
    # ========== Step 1: 镜头切分 ==========
    print("\n📍 Step 1/9: 镜头切分 (PySceneDetect)...")
    scenes, _ = detect_scenes(input_video, str(work_dir))
    GPUManager.clear()
    
    # 🔧 注意：静音剪除移到最后对成品视频处理，避免时间戳不匹配
    
    # ========== Step 2: 语音识别 ==========
    print("\n📍 Step 2/9: 语音识别 (faster-whisper)...")
    try:
        segments, transcript = transcribe_video(
            input_video,  # 🔧 使用原始视频
            str(work_dir / "subtitles.srt")
        )
    except Exception as e:
        print(f"⚠️ 语音识别失败（可能视频没有音轨）: {e}")
        segments, transcript = [], ""  # 🔧 边界情况：无音轨视频
    GPUManager.clear()
    
    # ========== Step 3: CLIP画面分析 ==========
    print("\n📍 Step 3/9: CLIP画面分析...")
    analyzer = CLIPAnalyzer()
    analyzed_scenes = analyzer.analyze_video_scenes(input_video, scenes)  # 🔧 使用原始视频
    del analyzer
    GPUManager.clear()
    
    # ========== Step 4: 联网获取电影信息（可选）==========
    if use_internet and movie_name:
        print("\n📍 Step 4/9: 联网获取电影信息...")
        try:
            fetcher = MovieInfoFetcher()
            movie_info = fetcher.search_movie(movie_name)
            print(f"   🎬 {movie_info.get('title')} - 评分: {movie_info.get('rating')}")
        except Exception as e:
            print(f"⚠️ 联网搜索失败: {e}")
            movie_info = None
    else:
        print("\n📍 Step 4/9: 跳过联网搜索（使用本地分析）")
        movie_info = None
    
    # ========== Step 5: AI生成文案 ==========
    print("\n📍 Step 5/9: AI生成解说文案 (Ollama + Qwen)...")
    script = generate_narration_script_enhanced(
        transcript,
        analyzed_scenes,
        movie_name=movie_name,
        style=style,
        use_internet=use_internet
    )
    
    # 保存文案
    script_file = work_dir / "解说文案.txt"
    script_file.write_text(script, encoding='utf-8')
    GPUManager.clear()
    
    # ========== Step 6: 自动检测保留原声片段 ==========
    print("\n📍 Step 6/9: 自动检测保留原声片段...")
    keep_original = auto_detect_keep_original(segments, analyzed_scenes)
    
    # ========== Step 7: 智能剪辑 ==========
    print("\n📍 Step 7/9: 智能剪辑...")
    important_scenes = [s for s in analyzed_scenes if s.get('is_important')]
    
    # 🔧 边界情况：如果没有重要镜头，使用所有镜头
    if len(important_scenes) == 0:
        print("   ⚠️ 未检测到重要镜头，使用所有镜头")
        important_scenes = analyzed_scenes
    
    selected_clips = select_best_clips(important_scenes, target_duration)
    
    # 🔧 边界情况：如果选中片段为空，至少选取前几个
    if len(selected_clips) == 0:
        print("   ⚠️ 片段选取为空，使用前5个镜头")
        selected_clips = [{'start': s['start'], 'end': s['end']} for s in analyzed_scenes[:5]]
    
    clip_dir = work_dir / "clips"
    extract_clips(input_video, selected_clips, str(clip_dir))  # 🔧 使用原始视频
    
    clip_files = sorted(clip_dir.glob("*.mp4"))
    concat_clips([str(f) for f in clip_files], str(work_dir / "剪辑后.mp4"))
    
    # ========== Step 8: 语音合成 + 视频合成 ==========
    print("\n📍 Step 8/9: 语音合成 + 视频合成...")
    
    # 语音合成
    tts = TTSEngine("edge")  # 使用Edge-TTS（更稳定）
    await tts.synthesize(script, str(work_dir / "narration.wav"))
    del tts
    GPUManager.clear()
    
    # 视频合成
    compose_final_video(
        str(work_dir / "剪辑后.mp4"),
        str(work_dir / "narration.wav"),
        str(work_dir / "成品_横屏.mp4"),
        keep_original_segments=keep_original,
        subtitle_path=str(work_dir / "subtitles.srt"),
        mode="mix"
    )
    
    # 转换抖音格式
    douyin_output = work_dir / "成品_抖音格式.mp4"
    convert_to_douyin(str(work_dir / "成品_横屏.mp4"), str(douyin_output))
    
    # ========== Step 9: 静音剪除（对成品视频优化节奏）==========
    print("\n📍 Step 9/9: 静音剪除优化...")
    final_output = work_dir / f"{output_name}.mp4"
    remove_silence(str(douyin_output), str(final_output))  # 🔧 最后阶段才做静音剪除
    
    # ========== 额外功能（可选）==========
    # 自动生成封面
    try:
        from cover_generator import auto_generate_cover
        auto_generate_cover(str(final_output), str(work_dir / "cover.jpg"))
    except Exception as e:
        print(f"⚠️ 封面生成跳过: {e}")
    
    # ========== 完成 ==========
    print("\n" + "=" * 70)
    print("🎉 全自动处理完成！")
    print("=" * 70)
    print(f"📁 最终视频: {final_output}")
    print(f"📝 解说文案: {script_file}")
    if (work_dir / "cover.jpg").exists():
        print(f"🖼️ 视频封面: {work_dir / 'cover.jpg'}")
    print(f"📂 工作目录: {work_dir}")
    print("=" * 70)
    
    return str(final_output)


# 运行
if __name__ == "__main__":
    # 默认测试
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
        print(f"⚠️ 视频文件不存在: {test_video}")
        print("\n使用方法:")
        print("  python app/main_auto.py 视频文件.mp4")
        print("  python app/main_auto.py 视频文件.mp4 电影名称")

