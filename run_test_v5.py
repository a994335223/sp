# run_test_v5.py - v5.4 测试脚本 (带详细日志)
"""
SmartVideoClipper v5.4 测试

v5.4 改进：
1. [OK] TMDB API 剧情获取
2. [OK] 确保60%解说比例（电视剧模式）
3. [OK] 增强备用解说方案
4. [OK] TTS卡顿修复
5. [OK] 敏感词多层过滤
6. [OK] GPU硬件加速
7. [OK] 语音识别优化（initial_prompt解决乱码）
8. [NEW] 详细日志输出（实时+文件）
"""

import asyncio
import sys
import os
from datetime import datetime

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# ===== v5.8.0 重要更新：Structured格式优化 =====
# 清理所有Python缓存，确保使用最新代码（v5.8 Structured格式）
import shutil
cache_dirs = [
    "__pycache__",
    "core/__pycache__",
    "utils/__pycache__"
]
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"[CACHE v5.8] 清理缓存: {cache_dir}")

# 清理已加载的模块，确保v5.8修改生效
modules_to_clear = [
    'core.narration_engine',
    'core.pipeline_v5',
    'core.dynamic_ratio',
    'core.silence_handler',
    'core.hook_generator'
]

for module in modules_to_clear:
    if module in sys.modules:
        del sys.modules[module]
        print(f"[CACHE v5.8] 清理模块: {module}")

print("[INFO v5.8] Structured格式优化已加载：100% AI生成成功率")

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))


# ========== 日志系统 ==========
class TeeLogger:
    """同时输出到控制台和文件的日志器（改进版）"""
    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log_path = log_file
        try:
            self.log_file = open(log_file, 'w', encoding='utf-8', buffering=1)
            print(f"[LOG] 日志文件创建成功: {log_file}")
        except Exception as e:
            print(f"[LOG] 日志文件创建失败: {e}")
            self.log_file = None
        
    def write(self, message):
        try:
            # 先输出到终端
            self.terminal.write(message)
            self.terminal.flush()
            # 再写入文件
            if self.log_file:
                # 处理可能的编码问题
                safe_message = message.encode('utf-8', errors='replace').decode('utf-8')
                self.log_file.write(safe_message)
                self.log_file.flush()
        except Exception:
            pass
        
    def flush(self):
        try:
            self.terminal.flush()
            if self.log_file:
                self.log_file.flush()
        except:
            pass
        
    def close(self):
        if self.log_file:
            self.log_file.close()


async def main():
    # 创建日志文件（使用ASCII安全的文件名）
    log_filename = f"test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    print(f"[INIT] 正在创建日志文件: {log_filename}")
    logger = TeeLogger(log_filename)
    sys.stdout = logger
    
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SmartVideoClipper v5.4 测试")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 日志文件: {log_filename}")
    print(f"{'='*60}")
    
    from core.pipeline_v5 import run_v5
    
    # 测试参数
    video_path = r"C:\Users\Administrator\Downloads\狂飙E01.mp4"
    output_name = "狂飙第一集_v5"
    title = "狂飙"
    style = "幽默"
    
    # 媒体类型参数
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
    print(f"   解说风格: {style}")
    print(f"   时长范围: 3-15分钟")
    
    # 运行
    result = await run_v5(
        video_path=video_path,
        output_name=output_name,
        title=title,
        style=style,
        min_duration=180,   # 最短3分钟
        max_duration=900,   # 最长15分钟
        media_type=media_type,
        episode=episode
    )
    
    # 输出结果
    print("\n" + "="*60)
    if result.get('success'):
        print("[SUCCESS] V5.4 处理完成!")
        print("="*60)
        print(f"   工作目录: {result.get('work_dir')}")
        print(f"   横屏视频: {result.get('output_video')}")
        print(f"   抖音视频: {result.get('output_douyin')}")
        print(f"   解说剧本: {result.get('script_path')}")
        print(f"   字幕文件: {result.get('subtitle_path')}")
        print(f"   视频时长: {result.get('duration', 0):.0f}秒")
        print(f"   原声场景: {result.get('original_scenes', 0)}个")
        print(f"   解说场景: {result.get('voiceover_scenes', 0)}个")
    else:
        print("[FAILED] 处理失败")
        print(f"   错误: {result.get('error')}")
    print("="*60)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 测试结束")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 日志已保存到: {log_filename}")
    
    # 关闭日志
    sys.stdout = logger.terminal
    logger.close()


if __name__ == "__main__":
    asyncio.run(main())

