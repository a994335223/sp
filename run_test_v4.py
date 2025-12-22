# run_test_v4.py - 测试V4.0解说驱动剪辑
"""
SmartVideoClipper v4.0 测试脚本

核心改进：
1. 看画面写解说（不是写解说找画面）
2. 解说和原声二选一（不混合）
3. 画面-解说精确对齐
4. TMDB API 获取详细剧情
"""

import asyncio
import sys
import os
import time
from datetime import datetime
from pathlib import Path

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))


class CLIProgressCallback:
    """命令行进度显示"""
    
    def __init__(self):
        self.current_step = 0
        self.total_steps = 8
        self.step_name = ""
        self.detail = ""
        self.start_time = time.time()

    def __call__(self, current_step: int, total_steps: int, step_name: str, detail: str):
        self.current_step = current_step
        self.total_steps = total_steps
        self.step_name = step_name
        self.detail = detail
        self.print_progress()

    def print_progress(self):
        percentage = int((self.current_step / self.total_steps) * 100)
        progress_bar_length = 30
        filled_length = int(progress_bar_length * self.current_step / self.total_steps)
        bar = '█' * filled_length + '░' * (progress_bar_length - filled_length)
        
        elapsed_time = time.time() - self.start_time
        
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 进度: [{bar}] {percentage}%")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 步骤 {self.current_step}/{self.total_steps}: {self.step_name}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.detail}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已耗时: {int(elapsed_time)}秒")
        print(f"{'='*60}")


async def main():
    """主测试函数"""
    
    # 测试参数
    test_video = r"C:\Users\Administrator\Downloads\狂飙E01.mp4"
    movie_name = "狂飙"
    output_name = "狂飙第一集_v4"
    target_duration = 600  # 10分钟
    style = "幽默"
    
    # TMDB API Key（如果已配置）
    tmdb_api_key = os.environ.get("TMDB_API_KEY", "")
    
    print("\n" + "="*60)
    print("🚀 SmartVideoClipper v4.0 - 看画面写解说")
    print("="*60)
    print(f"📹 输入视频: {test_video}")
    print(f"🎬 作品名称: {movie_name}")
    print(f"⏱️ 目标时长: {target_duration}秒")
    print(f"🎭 解说风格: {style}")
    print(f"🔑 TMDB API: {'已配置' if tmdb_api_key else '未配置'}")
    print("="*60)
    print("\n核心改进:")
    print("  1. ✅ 基于视频内容生成解说")
    print("  2. ✅ 解说和原声二选一")
    print("  3. ✅ 画面-解说精确对齐")
    print("="*60)
    
    # 检查视频是否存在
    if not os.path.exists(test_video):
        print(f"❌ 视频文件不存在: {test_video}")
        return
    
    # 导入新管线
    from core.pipeline_v4 import process_video_v4
    
    # 创建进度回调
    progress_tracker = CLIProgressCallback()
    
    try:
        # 运行处理
        result = await process_video_v4(
            input_video=test_video,
            movie_name=movie_name,
            output_name=output_name,
            style=style,
            target_duration=target_duration,
            progress_callback=progress_tracker,
            tmdb_api_key=tmdb_api_key
        )
        
        # 显示结果
        print("\n" + "="*60)
        print("✅ V4.0 处理完成！")
        print("="*60)
        print(f"📁 工作目录: {result.get('work_dir')}")
        print(f"🎬 横屏视频: {result.get('video_path')}")
        print(f"📱 抖音视频: {result.get('douyin_path')}")
        print(f"📝 解说剧本: {result.get('script_path')}")
        print(f"📄 字幕文件: {result.get('subtitle_path')}")
        print(f"🎯 分析场景: {result.get('analyzed_scenes')} 个")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动 V4.0 测试...")
    asyncio.run(main())
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🏁 测试结束")

