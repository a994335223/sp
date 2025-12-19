# app/main.py - 简化版，一键处理2小时电影（不含联网功能）
"""
SmartVideoClipper - 简化版主程序

功能: 一键处理视频，生成抖音解说
特点: 不需要联网，纯本地处理

使用方法:
    python app/main.py
"""

import os
import sys
import asyncio
from pathlib import Path

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
from generate_script import generate_narration_script
from smart_cut import extract_clips, concat_clips, parse_keep_original_markers, select_best_clips
from tts_synthesis import TTSEngine
from compose_video import compose_final_video, convert_to_douyin


async def process_movie(
    input_video: str,
    output_name: str = "抖音解说",
    style: str = "幽默吐槽"
):
    """
    处理2小时电影，生成抖音解说视频（简化版）
    
    参数:
        input_video: 输入视频路径
        output_name: 输出文件名
        style: 解说风格
    """
    work_dir = Path(f"workspace_{output_name}")
    work_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print(f"🎬 开始处理: {input_video}")
    print(f"   解说风格: {style}")
    print("=" * 60)
    
    # ========== Step 1: 镜头切分 ==========
    print("\n📍 Step 1/8: 镜头切分...")
    scenes, _ = detect_scenes(input_video, str(work_dir))
    print(f"   检测到 {len(scenes)} 个镜头")
    
    # ========== Step 2: 静音剪除（可选）==========
    print("\n📍 Step 2/8: 静音剪除...")
    # 对于电影，可以跳过这步，直接用原片
    # processed_video = remove_silence(input_video, str(work_dir / "no_silence.mp4"))
    processed_video = input_video
    
    # ========== Step 3: 语音识别 ==========
    print("\n📍 Step 3/8: 语音识别...")
    segments, transcript = transcribe_video(
        processed_video, 
        str(work_dir / "subtitles.srt")
    )
    print(f"   识别到 {len(segments)} 段对白")
    
    # ========== Step 4: CLIP画面分析 ==========
    print("\n📍 Step 4/8: CLIP画面分析...")
    analyzer = CLIPAnalyzer()
    analyzed_scenes = analyzer.analyze_video_scenes(processed_video, scenes)
    important_scenes = [s for s in analyzed_scenes if s.get('is_important')]
    print(f"   发现 {len(important_scenes)} 个重要镜头")
    
    # 🔧 统一使用GPUManager清理显存
    del analyzer
    GPUManager.clear()
    
    # ========== Step 5: AI生成文案 ==========
    print("\n📍 Step 5/8: AI生成解说文案...")
    script = generate_narration_script(transcript, analyzed_scenes, style)
    
    # 保存文案
    script_file = work_dir / "解说文案.txt"
    script_file.write_text(script, encoding='utf-8')
    print(f"   文案已保存: {script_file}")
    
    # ========== Step 6: 智能剪辑 ==========
    print("\n📍 Step 6/8: 智能剪辑...")
    
    # 🔧 边界情况：如果没有重要镜头，使用所有镜头
    if len(important_scenes) == 0:
        print("   ⚠️ 未检测到重要镜头，使用所有镜头")
        important_scenes = analyzed_scenes
    
    # 选取重要镜头（控制总时长3-5分钟）
    selected_clips = select_best_clips(important_scenes, target_duration=240)
    
    # 🔧 边界情况：如果选中片段为空，至少选取前几个
    if len(selected_clips) == 0:
        print("   ⚠️ 片段选取为空，使用前5个镜头")
        selected_clips = [{'start': s['start'], 'end': s['end']} for s in analyzed_scenes[:5]]
    
    extract_clips(processed_video, selected_clips, str(work_dir / "clips"))
    
    clip_files = sorted((work_dir / "clips").glob("*.mp4"))
    concat_clips([str(f) for f in clip_files], str(work_dir / "剪辑后.mp4"))
    
    # ========== Step 7: 语音合成 ==========
    print("\n📍 Step 7/8: 语音合成...")
    tts = TTSEngine("edge")  # 使用Edge-TTS（更稳定）
    await tts.synthesize(script, str(work_dir / "narration.wav"))
    del tts
    GPUManager.clear()  # 🔧 TTS后清理显存
    
    # ========== Step 8: 视频合成 ==========
    print("\n📍 Step 8/8: 视频合成...")
    keep_original = parse_keep_original_markers(script)
    
    compose_final_video(
        str(work_dir / "剪辑后.mp4"),
        str(work_dir / "narration.wav"),
        str(work_dir / "成品_横屏.mp4"),
        keep_original_segments=keep_original,
        subtitle_path=str(work_dir / "subtitles.srt"),  # 🔧 添加字幕
        mode="mix"
    )
    
    # 转换抖音格式
    final_output = work_dir / f"{output_name}.mp4"
    convert_to_douyin(
        str(work_dir / "成品_横屏.mp4"),
        str(final_output)
    )
    
    print("\n" + "=" * 60)
    print("🎉 处理完成！")
    print(f"📁 输出文件: {final_output}")
    print(f"📝 解说文案: {script_file}")
    print("=" * 60)
    
    return str(final_output)


# 运行
if __name__ == "__main__":
    # 默认测试
    test_video = "test_video.mp4"
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
    
    if os.path.exists(test_video):
        asyncio.run(process_movie(
            test_video,
            output_name="解说视频",
            style="幽默吐槽"
        ))
    else:
        print(f"⚠️ 视频文件不存在: {test_video}")
        print("\n使用方法:")
        print("  python app/main.py 视频文件.mp4")

