# app/gradio_ui.py - 完整的Gradio界面
"""
SmartVideoClipper - Web界面

功能: 提供友好的Web界面，一键处理视频
特点: 无需命令行操作，小白也能用

使用方法:
    python app/gradio_ui.py
    然后打开浏览器访问 http://localhost:7860
"""

import gradio as gr
import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

# 🔧 导入主处理函数（使用相对导入）
from .main_auto import full_auto_process


def process_video_wrapper(video_file, movie_name, style, target_duration, use_internet):
    """Gradio界面的处理函数包装器"""
    if video_file is None:
        return None, "❌ 请先上传视频", None, None
    
    try:
        # 调用主处理函数
        output_path = asyncio.run(full_auto_process(
            input_video=video_file,
            movie_name=movie_name if movie_name else None,
            output_name="gradio_output",
            style=style,
            use_internet=use_internet,
            target_duration=int(target_duration)
        ))
        
        # 返回结果
        work_dir = Path(f"workspace_gradio_output")
        return (
            output_path,
            "✅ 处理完成！",
            str(work_dir / "cover.jpg") if (work_dir / "cover.jpg").exists() else None,
            str(work_dir / "subtitles.srt") if (work_dir / "subtitles.srt").exists() else None
        )
    except Exception as e:
        return None, f"❌ 处理失败: {str(e)}", None, None


def create_demo():
    """创建Gradio界面"""
    
    with gr.Blocks(
        title="SmartVideoClipper - 智能视频解说生成器",
        theme=gr.themes.Soft()
    ) as demo:
        
        # 标题
        gr.Markdown("""
        # 🎬 SmartVideoClipper v4.0
        ### 智能视频解说生成器 - 比NarratoAI更强大！
        
        > 📺 支持2小时电影 / 50分钟电视剧
        > 🤖 全自动处理，无需人工干预
        > 🎭 多种解说风格可选
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                # 输入区域
                gr.Markdown("### 📤 输入")
                
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
                    "🚀 开始处理",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                # 输出区域
                gr.Markdown("### 📥 输出")
                
                video_output = gr.Video(
                    label="生成的解说视频"
                )
                
                status = gr.Textbox(
                    label="处理状态",
                    value="等待上传视频...",
                    interactive=False
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
        
        1. **上传视频**: 支持 MP4, MKV, AVI 等常见格式
        2. **填写名称**: 可选，填写后会联网搜索电影信息，提升解说质量
        3. **选择风格**: 根据视频类型选择合适的解说风格
        4. **调整时长**: 生成视频的目标时长（建议3-5分钟）
        5. **开始处理**: 点击按钮，等待处理完成
        
        ⏱️ **处理时间参考**:
        - 50分钟电视剧: 约10-15分钟
        - 2小时电影: 约25-35分钟
        
        💡 **提示**: 首次使用需要下载AI模型，可能需要较长时间
        """)
        
        # 绑定事件
        process_btn.click(
            fn=process_video_wrapper,
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
            print("⚠️ 部分依赖缺失，功能可能不完整")
    except ImportError:
        pass
    
    # 创建并启动界面
    demo = create_demo()
    
    print("\n" + "=" * 50)
    print("🚀 SmartVideoClipper Web界面已启动！")
    print("=" * 50)
    print("📌 请在浏览器中打开: http://localhost:7860")
    print("📌 按 Ctrl+C 可以停止服务")
    print("=" * 50 + "\n")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )

