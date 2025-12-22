# -*- coding: utf-8 -*-
"""
SmartVideoClipper v2.0 - 测试运行脚本
带实时进度显示 + 多维度重要性评分
"""
import asyncio
import sys
import os
import time
import shutil
from datetime import datetime

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

sys.path.insert(0, '.')
sys.path.insert(0, './core')

from app.main_auto import full_auto_process, PROCESS_STEPS, TOTAL_STEPS


def progress_callback(step: int, total: int, name: str, detail: str):
    """进度回调函数 - 带时间戳和进度条"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    percentage = int((step / total) * 100)
    bar_length = 30
    filled = int(bar_length * step / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    print(f"\n{'='*60}")
    print(f"[{timestamp}] 进度: [{bar}] {percentage}%")
    print(f"[{timestamp}] 步骤 {step}/{total}: {name}")
    print(f"[{timestamp}] {detail}")
    print(f"{'='*60}")


async def main():
    # ============ 配置区域 ============
    input_video = r'C:\Users\Administrator\Downloads\狂飙E01.mp4'
    movie_name = '狂飙'
    output_name = '狂飙第一集解说_v2'  # 新版本输出
    style = '专业解说'  # 改为专业解说风格
    target_duration = 600
    # ==================================
    
    # 清理旧的工作目录
    work_dir = f'workspace_{output_name}'
    if os.path.exists(work_dir):
        print(f"[CLEAN] 清理旧工作目录: {work_dir}")
        shutil.rmtree(work_dir)
    
    print("\n" + "★" * 60)
    print("★  SmartVideoClipper v2.0 - 智能视频解说生成器")
    print("★  ")
    print("★  新特性:")
    print("★  - 多维度重要性评分（音频+对话+情感+场景变化）")
    print("★  - 增强片头片尾检测（音频特征分析）")
    print("★  - 专业文案生成（无垃圾标注）")
    print("★  " + "=" * 54)
    print(f"★  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"★  输入视频: {input_video}")
    print(f"★  电影名称: {movie_name}")
    print(f"★  解说风格: {style}")
    print(f"★  目标时长: {target_duration}秒")
    print("★" * 60 + "\n")
    
    start_time = time.time()
    
    try:
        result = await full_auto_process(
            input_video=input_video,
            movie_name=movie_name,
            output_name=output_name,
            style=style,
            use_internet=True,
            target_duration=target_duration,
            progress_callback=progress_callback
        )
        
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        print("\n" + "★" * 60)
        print("★  ✅ 处理完成！")
        print("★  " + "=" * 54)
        print(f"★  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"★  总耗时: {minutes}分{seconds}秒")
        print(f"★  输出文件: {result}")
        print("★" * 60 + "\n")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print("\n" + "❌" * 30)
        print(f"处理失败: {e}")
        print(f"已运行: {int(elapsed)}秒")
        print("❌" * 30 + "\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动处理...")
    asyncio.run(main())
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 脚本结束")
