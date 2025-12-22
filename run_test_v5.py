# run_test_v5.py - v5.1 测试脚本 (电影/电视剧分离版)
"""
SmartVideoClipper v5.1 测试

🎬 核心升级：电影与电视剧模式分离

已修复的核心问题：
1. ✅ 电影/电视剧模式分离（解说策略不同）
2. ✅ 音频分段切换（每个片段独立处理）
3. ✅ TTS分段生成（解说-画面精确对齐）
4. ✅ 修复语音停顿问题
5. ✅ 敏感词多层过滤
6. ✅ GPU硬件加速
"""

import asyncio
import sys
import os
from datetime import datetime

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))


async def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 启动 V5.1 测试（电视剧模式）...")
    
    from core.pipeline_v5 import run_v5
    
    # 测试参数
    video_path = r"C:\Users\Administrator\Downloads\狂飙E01.mp4"
    output_name = "狂飙第一集_v5"
    title = "狂飙"
    style = "幽默"
    
    # 🆕 媒体类型参数
    media_type = "tv"  # 电视剧模式：60%解说+40%原声
    episode = 1        # 第1集
    
    # 检查视频是否存在
    if not os.path.exists(video_path):
        print(f"[ERROR] 视频不存在: {video_path}")
        return
    
    print(f"\n[配置]")
    print(f"   媒体类型: 电视剧")
    print(f"   当前集数: 第{episode}集")
    print(f"   解说策略: 讲述本集故事（60%解说+40%原声）")
    
    # 运行
    result = await run_v5(
        video_path=video_path,
        output_name=output_name,
        title=title,
        style=style,
        min_duration=180,   # 最短3分钟
        max_duration=900,   # 最长15分钟
        media_type=media_type,  # 🆕 电视剧模式
        episode=episode         # 🆕 第1集
    )
    
    # 输出结果
    print("\n" + "="*60)
    if result.get('success'):
        print("✅ V5.0 处理完成！")
        print("="*60)
        print(f"📁 工作目录: {result.get('work_dir')}")
        print(f"🎬 横屏视频: {result.get('output_video')}")
        print(f"📱 抖音视频: {result.get('output_douyin')}")
        print(f"📝 解说剧本: {result.get('script_path')}")
        print(f"📄 字幕文件: {result.get('subtitle_path')}")
        print(f"⏱️ 视频时长: {result.get('duration', 0):.0f}秒")
        print(f"🔊 原声场景: {result.get('original_scenes', 0)}个")
        print(f"🎙️ 解说场景: {result.get('voiceover_scenes', 0)}个")
    else:
        print("❌ 处理失败")
        print(f"错误: {result.get('error')}")
    print("="*60)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🏁 测试结束")


if __name__ == "__main__":
    asyncio.run(main())

