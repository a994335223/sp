# app/gradio_ui.py - 完整的Gradio界面
"""
SmartVideoClipper - Web界面

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

# 导入主处理函数
from .main_auto import full_auto_process, PROCESS_STEPS, TOTAL_STEPS


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
        for i, (step_num, name, desc) in enumerate(PROCESS_STEPS, 1):
            if i < self.current_step:
                status = "[OK]"
            elif i == self.current_step:
                status = "[>>]"  # 当前步骤
            else:
                status = "[  ]"
            lines.append(f"  {status} Step {i}: {name}")
        return "\n".join(lines)


def run_async_process(tracker: ProgressTracker, video_file: str, movie_name: str, 
                      style: str, target_duration: int, use_internet: bool):
    """在新线程中运行异步处理"""
    
    def progress_callback(current_step, total_steps, step_name, detail):
        tracker.update(current_step, total_steps, step_name, detail)
    
    async def async_task():
        try:
            result = await full_auto_process(
                input_video=video_file,
                movie_name=movie_name if movie_name else None,
                output_name="gradio_output",
                style=style,
                use_internet=use_internet,
                target_duration=int(target_duration),
                progress_callback=progress_callback
            )
            tracker.result = result
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


def process_video_with_progress(video_file, movie_name, style, target_duration, use_internet) -> Generator:
    """带进度显示的视频处理函数（生成器）"""
    
    if video_file is None:
        yield None, "[ERROR] 请先上传视频", None, None
        return
    
    # 创建进度追踪器
    tracker = ProgressTracker()
    tracker.is_running = True
    
    # 在新线程中运行处理任务
    process_thread = threading.Thread(
        target=run_async_process,
        args=(tracker, video_file, movie_name, style, target_duration, use_internet)
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
        work_dir = Path("workspace_gradio_output")
        cover_path = str(work_dir / "cover.jpg") if (work_dir / "cover.jpg").exists() else None
        subtitle_path = str(work_dir / "subtitles.srt") if (work_dir / "subtitles.srt").exists() else None
        
        final_status = f"""[OK] 处理完成！

--- 处理结果 ---
{tracker._get_steps_status()}

输出文件: {tracker.result}
"""
        yield tracker.result, final_status, cover_path, subtitle_path
    else:
        yield None, "[ERROR] 处理异常终止", None, None


def create_demo():
    """创建Gradio界面"""
    
    with gr.Blocks(
        title="SmartVideoClipper - 智能视频解说生成器",
        theme=gr.themes.Soft()
    ) as demo:
        
        # 标题
        gr.Markdown("""
        # SmartVideoClipper v4.0
        ### 智能视频解说生成器 - 比NarratoAI更强大！
        
        > 支持2小时电影 / 50分钟电视剧 | 全自动处理，无需人工干预 | 多种解说风格可选
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                # 输入区域
                gr.Markdown("### 输入")
                
                video_input = gr.Video(
                    label="上传视频",
                    sources=["upload"]
                )
                
                movie_name = gr.Textbox(
                    label="电影/剧名（可选，用于联网搜索信息）",
                    placeholder="例如：复仇者联盟",
                    value=""
                )
                
                style = gr.Dropdown(
                    label="解说风格",
                    choices=["幽默吐槽", "正经解说", "悬疑紧张", "温情感人"],
                    value="幽默吐槽"
                )
                
                target_duration = gr.Slider(
                    label="目标时长（秒）",
                    minimum=60,
                    maximum=600,
                    value=240,
                    step=30
                )
                
                use_internet = gr.Checkbox(
                    label="联网搜索电影信息（增强解说质量）",
                    value=True
                )
                
                process_btn = gr.Button(
                    "开始处理",
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
        ### 使用说明
        
        1. **上传视频**: 支持 MP4, MKV, AVI 等常见格式
        2. **填写名称**: 可选，填写后会联网搜索电影信息，提升解说质量
        3. **选择风格**: 根据视频类型选择合适的解说风格
        4. **调整时长**: 生成视频的目标时长（建议3-5分钟）
        5. **开始处理**: 点击按钮，等待处理完成
        
        **处理时间参考**:
        - 50分钟电视剧: 约10-15分钟
        - 2小时电影: 约25-35分钟
        
        **提示**: 首次使用需要下载AI模型，可能需要较长时间
        """)
        
        # 绑定事件 - 使用生成器实现实时进度更新
        process_btn.click(
            fn=process_video_with_progress,
            inputs=[video_input, movie_name, style, target_duration, use_internet],
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
