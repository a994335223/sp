# app/gradio_ui.py - 完整的Gradio界面 v5.1 (电影/电视剧分离版)
"""
SmartVideoClipper v5.1 - Web界面

🎬 核心升级：电影与电视剧模式分离

功能: 提供友好的Web界面，一键处理视频
特点: 无需命令行操作，小白也能用

使用方法:
    python app/gradio_ui.py
    然后打开浏览器访问 http://localhost:7860
"""

import os
import sys

# 关键：在导入任何模型库之前设置 HuggingFace 镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

import gradio as gr
import asyncio
import time
import threading
from pathlib import Path
from typing import Generator

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

# 定义处理步骤（v5.1版本）
PROCESS_STEPS = [
    (0, "预处理", "检测并去除片头片尾"),
    (1, "语音识别", "识别视频中的对话"),
    (2, "场景分析", "分析视频场景和剧情"),
    (3, "智能解说", "生成解说文案（电影/电视剧模式）"),
    (4, "时长控制", "智能选择场景"),
    (5, "TTS合成", "生成解说语音"),
    (6, "片段处理", "处理视频片段"),
    (7, "输出成品", "生成最终视频"),
]
TOTAL_STEPS = len(PROCESS_STEPS)


class ProgressTracker:
    """进度追踪器"""
    def __init__(self):
        self.current_step = 0
        self.total_steps = TOTAL_STEPS
        self.step_name = ""
        self.detail = ""
        self.is_running = False
        self.error = None
        self.result = None
    
    def update(self, current_step: int, total_steps: int, step_name: str, detail: str):
        """更新进度"""
        self.current_step = current_step
        self.total_steps = total_steps
        self.step_name = step_name
        self.detail = detail
    
    def get_progress_text(self) -> str:
        """获取进度文本"""
        if self.error:
            return f"[ERROR] 处理失败: {self.error}"
        if not self.is_running:
            if self.result:
                return "[OK] 处理完成！"
            return "等待开始..."
        
        percentage = int((self.current_step / self.total_steps) * 100)
        progress_bar = "=" * (percentage // 5) + ">" + " " * (20 - percentage // 5)
        
        return f"""[处理中] {percentage}% [{progress_bar}]

当前步骤: {self.current_step}/{self.total_steps} - {self.step_name}
{self.detail}

--- 处理流程 ---
{self._get_steps_status()}
"""
    
    def _get_steps_status(self) -> str:
        """获取所有步骤状态"""
        lines = []
        for step_num, name, desc in PROCESS_STEPS:
            if step_num < self.current_step:
                status = "[OK]"
            elif step_num == self.current_step:
                status = "[>>]"  # 当前步骤
            else:
                status = "[  ]"
            lines.append(f"  {status} Step {step_num}: {name}")
        return "\n".join(lines)


def run_async_process(tracker: ProgressTracker, video_file: str, movie_name: str, 
                      style: str, target_duration: int, media_type: str, episode: int):
    """在新线程中运行异步处理（v5.1版本）"""
    
    def progress_callback(step, message, pct):
        tracker.update(step, TOTAL_STEPS, PROCESS_STEPS[min(step, len(PROCESS_STEPS)-1)][1], message)
    
    async def async_task():
        try:
            # 使用v5.1 pipeline
            from pipeline_v5 import VideoPipelineV5
            
            pipeline = VideoPipelineV5()
            
            # 生成输出名称
            output_name = movie_name if movie_name else "gradio_output"
            output_name = output_name.replace(" ", "_") + "_v5"
            
            result = await pipeline.process(
                video_path=video_file,
                output_name=output_name,
                title=movie_name if movie_name else "",
                style=style,
                min_duration=max(60, int(target_duration) - 60),
                max_duration=int(target_duration) + 120,
                media_type=media_type,
                episode=int(episode) if episode else 0,
                progress_callback=progress_callback
            )
            
            tracker.result = result.get('output_video', '')
        except Exception as e:
            tracker.error = str(e)
            import traceback
            traceback.print_exc()
        finally:
            tracker.is_running = False
    
    # 创建新的事件循环并运行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_task())
    finally:
        loop.close()


def process_video_with_progress(video_file, movie_name, style, target_duration, media_type, episode) -> Generator:
    """带进度显示的视频处理函数（生成器）- v5.1版本"""
    
    if video_file is None:
        yield None, "[ERROR] 请先上传视频", None, None
        return
    
    # 创建进度追踪器
    tracker = ProgressTracker()
    tracker.is_running = True
    
    # 显示开始信息
    media_type_cn = "电视剧" if media_type == "tv" else "电影"
    start_msg = f"[开始] {media_type_cn}模式 - "
    if media_type == "tv":
        start_msg += f"第{episode}集（60%解说+40%原声）"
    else:
        start_msg += f"精彩片段集锦（40%解说+60%原声）"
    
    yield None, start_msg, None, None
    
    # 在新线程中运行处理任务
    process_thread = threading.Thread(
        target=run_async_process,
        args=(tracker, video_file, movie_name, style, target_duration, media_type, episode)
    )
    process_thread.start()
    
    # 持续更新进度
    while tracker.is_running:
        yield None, tracker.get_progress_text(), None, None
        time.sleep(0.5)  # 每0.5秒更新一次进度
    
    # 等待线程完成
    process_thread.join()
    
    # 返回最终结果
    if tracker.error:
        yield None, f"[ERROR] 处理失败: {tracker.error}", None, None
    elif tracker.result:
        # 找到实际的工作目录
        work_dirs = list(PROJECT_ROOT.glob("workspace_*_v5"))
        work_dir = work_dirs[-1] if work_dirs else None
        
        cover_path = None
        subtitle_path = None
        if work_dir:
            cover_file = work_dir / "cover.jpg"
            subtitle_file = work_dir / "subtitles.srt"
            cover_path = str(cover_file) if cover_file.exists() else None
            subtitle_path = str(subtitle_file) if subtitle_file.exists() else None
        
        final_status = f"""[OK] 处理完成！

--- 处理结果 ---
{tracker._get_steps_status()}

媒体类型: {media_type_cn}
输出文件: {tracker.result}
"""
        yield tracker.result, final_status, cover_path, subtitle_path
    else:
        yield None, "[ERROR] 处理异常终止", None, None


def create_demo():
    """创建Gradio界面 - v5.1版本"""
    
    with gr.Blocks(
        title="SmartVideoClipper v5.1 - 智能视频解说",
        theme=gr.themes.Soft()
    ) as demo:
        
        # 标题
        gr.Markdown("""
        # 🎬 SmartVideoClipper v5.1
        ### 全球第一的智能视频解说生成器 - 电影/电视剧分离版
        
        > 🎥 **电影模式**: 精彩片段集锦（40%解说+60%原声）  
        > 📺 **电视剧模式**: 讲述本集故事（60%解说+40%原声）  
        > ✨ 全自动处理，GPU加速，无需人工干预
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                # 输入区域
                gr.Markdown("### 📁 输入设置")
                
                video_input = gr.Video(
                    label="上传视频",
                    sources=["upload"]
                )
                
                movie_name = gr.Textbox(
                    label="作品名称（可选，用于获取剧情信息）",
                    placeholder="例如：狂飙、复仇者联盟",
                    value=""
                )
                
                # 🆕 媒体类型选择（核心功能）
                gr.Markdown("### 🎯 媒体类型（重要！）")
                
                media_type = gr.Radio(
                    label="选择类型",
                    choices=[
                        ("🎥 电影（精彩片段集锦）", "movie"),
                        ("📺 电视剧（讲述本集故事）", "tv")
                    ],
                    value="tv",
                    info="电视剧会有更多解说，电影保留更多原声"
                )
                
                episode = gr.Number(
                    label="第几集/第几部（电视剧必填，电影可选）",
                    value=1,
                    minimum=1,
                    maximum=999,
                    step=1,
                    info="电视剧：第几集 | 系列电影：第几部"
                )
                
                gr.Markdown("### ⚙️ 其他设置")
                
                style = gr.Dropdown(
                    label="解说风格",
                    choices=["幽默", "专业解说", "悬疑紧张", "温情感人"],
                    value="幽默"
                )
                
                target_duration = gr.Slider(
                    label="目标时长（秒）",
                    minimum=60,
                    maximum=900,
                    value=300,
                    step=30,
                    info="建议：电视剧3-5分钟，电影5-10分钟"
                )
                
                process_btn = gr.Button(
                    "🚀 开始处理",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                # 输出区域
                gr.Markdown("### 输出")
                
                video_output = gr.Video(
                    label="生成的解说视频"
                )
                
                status = gr.Textbox(
                    label="处理状态",
                    value="等待上传视频...",
                    interactive=False,
                    lines=15,  # 增加行数显示更多进度信息
                    max_lines=20
                )
                
                cover_output = gr.Image(
                    label="自动生成的封面"
                )
                
                subtitle_output = gr.File(
                    label="字幕文件下载"
                )
        
        # 使用说明
        gr.Markdown("""
        ---
        ### 📖 使用说明
        
        #### 🎯 核心概念：电影 vs 电视剧模式
        
        | 模式 | 解说比例 | 适用场景 | 效果 |
        |------|----------|----------|------|
        | 🎥 电影 | 40%解说+60%原声 | 精彩片段集锦 | 保留经典台词 |
        | 📺 电视剧 | 60%解说+40%原声 | 3分钟看完一集 | 快速了解剧情 |
        
        #### 📝 操作步骤
        
        1. **上传视频**: 支持 MP4, MKV, AVI 等常见格式
        2. **选择类型**: ⚠️ **重要！** 根据视频内容选择电影或电视剧
        3. **填写集数**: 电视剧必须填写第几集，电影可选
        4. **选择风格**: 根据视频氛围选择合适的解说风格
        5. **开始处理**: 点击按钮，等待处理完成
        
        #### ⏱️ 处理时间参考（GPU加速）
        - 50分钟电视剧: 约10-15分钟
        - 2小时电影: 约20-30分钟
        
        #### 💡 提示
        - 文件名包含"E01"等标记会自动识别为电视剧
        - 首次使用需要下载AI模型，可能需要较长时间
        """)
        
        # 绑定事件 - 使用生成器实现实时进度更新
        process_btn.click(
            fn=process_video_with_progress,
            inputs=[video_input, movie_name, style, target_duration, media_type, episode],
            outputs=[video_output, status, cover_output, subtitle_output]
        )
    
    return demo


# 启动
if __name__ == "__main__":
    # 检查依赖
    try:
        from utils.dependency_check import check_dependencies
        success, missing = check_dependencies()
        if not success:
            print("[WARNING] 部分依赖缺失，功能可能不完整")
    except ImportError:
        pass
    
    # 创建并启动界面
    demo = create_demo()
    
    print("\n" + "=" * 50)
    print("SmartVideoClipper Web界面已启动！")
    print("=" * 50)
    print("请在浏览器中打开: http://localhost:7860")
    print("按 Ctrl+C 可以停止服务")
    print("=" * 50 + "\n")
    
    # 解决 Gradio 6.0 的 502 启动问题
    import os
    os.environ["no_proxy"] = "localhost,127.0.0.1"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
    
    demo.launch(
        server_name="127.0.0.1",  # 使用 127.0.0.1 而不是 0.0.0.0
        server_port=7860,
        share=False,
        show_error=True
    )
