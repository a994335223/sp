# run_test_v3.py - 测试新版解说驱动剪辑管线
"""
SmartVideoClipper v3.0 测试脚本

核心改进：
1. 联网搜索前置 - 先了解剧情
2. 剧情理解 - 深度分析故事结构
3. 解说驱动 - 先写解说再配画面
4. 语义匹配 - 精确匹配画面内容
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
        self.total_steps = 9
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
    output_name = "狂飙第一集_v3"
    target_duration = 600  # 10分钟
    style = "幽默"
    
    print("\n" + "="*60)
    print("🚀 SmartVideoClipper v3.0 - 解说驱动剪辑")
    print("="*60)
    print(f"📹 输入视频: {test_video}")
    print(f"🎬 作品名称: {movie_name}")
    print(f"⏱️ 目标时长: {target_duration}秒")
    print(f"🎭 解说风格: {style}")
    print("="*60)
    
    # 检查视频是否存在
    if not os.path.exists(test_video):
        print(f"❌ 视频文件不存在: {test_video}")
        return
    
    # 导入新管线
    from core.pipeline_v3 import process_video_v3
    
    # 创建进度回调
    progress_tracker = CLIProgressCallback()
    
    try:
        # 运行处理
        result = await process_video_v3(
            input_video=test_video,
            movie_name=movie_name,
            output_name=output_name,
            style=style,
            target_duration=target_duration,
            progress_callback=progress_tracker
        )
        
        # 显示结果
        print("\n" + "="*60)
        print("✅ 处理完成！")
        print("="*60)
        print(f"📁 工作目录: {result.get('work_dir')}")
        print(f"🎬 横屏视频: {result.get('video_path')}")
        print(f"📱 抖音视频: {result.get('douyin_path')}")
        print(f"📝 解说剧本: {result.get('script_path')}")
        print(f"📄 字幕文件: {result.get('subtitle_path')}")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动测试...")
    asyncio.run(main())
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🏁 测试结束")

