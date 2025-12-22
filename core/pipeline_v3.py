# core/pipeline_v3.py - 新一代处理管线
"""
SmartVideoClipper v3.0 - 解说驱动剪辑管线

核心理念：
真人解说博主的工作流程 = 先理解故事 → 写解说稿 → 找配图 → 剪辑

新流程：
1. 预处理：去片头片尾
2. 联网搜索：获取剧情、人物、评价（前置！）
3. 语音识别：获取字幕
4. 剧情理解：深度理解故事结构
5. 生成剧本：创作分段解说
6. 素材匹配：为每段解说找最佳画面
7. 智能剪辑：按剧本精确剪辑
8. 合成输出：TTS + 混音 + 字幕

与旧版的区别：
- 旧版：先剪片段 → 再写解说（剪辑驱动）
- 新版：先写解说 → 再配画面（解说驱动）
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

# 设置环境
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

# 导入模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

from intro_outro_detect import auto_trim_intro_outro
from story_understanding import StoryUnderstanding
from script_generator import ScriptGenerator
from semantic_matcher import SemanticMatcher, SmartClipper
from scene_detect import detect_scenes
from transcribe import transcribe_video
from tts_synthesis import TTSEngine
from smart_cut import extract_clips, concat_clips, VIDEO_ENCODER
from compose_video import compose_final_video, add_subtitles, convert_to_douyin
from remove_silence import remove_silence


# 处理步骤
PROCESS_STEPS_V3 = [
    (0, "预处理", "检测并去除片头片尾"),
    (1, "联网搜索", "获取剧情和人物信息"),  # 前置！
    (2, "语音识别", "识别视频对白"),
    (3, "剧情理解", "深度分析故事结构"),
    (4, "生成剧本", "创作专业解说剧本"),
    (5, "素材匹配", "为解说配最佳画面"),
    (6, "智能剪辑", "精确剪辑视频素材"),
    (7, "语音合成", "生成解说配音"),
    (8, "合成输出", "混音、字幕、转码"),
]
TOTAL_STEPS_V3 = len(PROCESS_STEPS_V3)


class VideoPipelineV3:
    """
    新一代视频处理管线
    """
    
    def __init__(self):
        self.story_engine = StoryUnderstanding()
        self.script_generator = ScriptGenerator()
        self.semantic_matcher = SemanticMatcher()
        self.smart_clipper = SmartClipper()
        self.tts_engine = TTSEngine()
    
    async def process(
        self,
        input_video: str,
        movie_name: str = None,
        output_name: str = "解说视频",
        style: str = "幽默",
        target_duration: int = 300,
        progress_callback: Optional[Callable] = None,
        skip_intro_outro: bool = False
    ) -> dict:
        """
        执行完整处理流程
        
        参数：
            input_video: 输入视频路径
            movie_name: 电影/剧集名称（用于联网搜索）
            output_name: 输出文件名
            style: 解说风格
            target_duration: 目标时长（秒）
            progress_callback: 进度回调函数
            skip_intro_outro: 是否跳过片头片尾检测
        
        返回：
            {
                'video_path': '...',
                'script_path': '...',
                'subtitle_path': '...',
                'work_dir': '...',
            }
        """
        start_time = datetime.now()
        
        # 创建工作目录
        work_dir = Path(f"workspace_{output_name}_v3")
        work_dir.mkdir(exist_ok=True)
        
        def report_progress(step: int, detail: str):
            if progress_callback:
                step_name = PROCESS_STEPS_V3[step][1] if step < len(PROCESS_STEPS_V3) else "完成"
                progress_callback(step, TOTAL_STEPS_V3, step_name, detail)
            print(f"\n[Step {step}] {detail}")
        
        # 打印头部信息
        self._print_header(input_video, movie_name, style, target_duration)
        
        try:
            # ========== Step 0: 预处理 ==========
            report_progress(0, "正在检测片头片尾...")
            
            if skip_intro_outro:
                processed_video = input_video
                intro_offset = 0
            else:
                trimmed_path = str(work_dir / "trimmed_video.mp4")
                processed_video, intro_offset, outro_time = auto_trim_intro_outro(
                    input_video, trimmed_path, skip_if_short=300
                )
                if processed_video != input_video:
                    print(f"   ✓ 已去除片头: {intro_offset:.1f}秒")
            
            # ========== Step 1: 联网搜索（前置！）==========
            report_progress(1, f"正在搜索《{movie_name or '未知'}》的信息...")
            
            # 这里会在 story_understanding 中完成联网搜索
            # 暂时保存movie_name，后面使用
            
            # ========== Step 2: 语音识别 ==========
            report_progress(2, "正在识别视频对白...")
            
            subtitle_path = str(work_dir / "subtitles.srt")
            segments, transcript = transcribe_video(
                processed_video,
                output_srt=subtitle_path
            )
            print(f"   ✓ 识别到 {len(segments)} 段对白")
            
            # ========== Step 3: 剧情理解 ==========
            report_progress(3, "正在深度分析剧情...")
            
            story_understanding = self.story_engine.understand(
                movie_name=movie_name or "未知作品",
                transcript_segments=segments,
                full_transcript=transcript
            )
            
            # 保存剧情理解结果
            import json
            with open(work_dir / "story_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(story_understanding, f, ensure_ascii=False, indent=2)
            
            # ========== Step 4: 生成剧本 ==========
            report_progress(4, f"正在创作{style}风格解说剧本...")
            
            script_segments = self.script_generator.generate(
                story_understanding=story_understanding,
                target_duration=target_duration,
                style=style
            )
            
            # 保存剧本
            script_text = self._format_script(script_segments)
            script_path = work_dir / "解说剧本.txt"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_text)
            print(f"   ✓ 剧本已保存: {script_path}")
            
            # ========== Step 5: 素材匹配 ==========
            report_progress(5, "正在为解说匹配最佳画面...")
            
            # 先做场景检测
            scenes, _ = detect_scenes(processed_video, str(work_dir))
            
            # 语义匹配
            matched_segments = self.semantic_matcher.match_segments(
                video_path=processed_video,
                script_segments=script_segments,
                transcript_segments=segments,
                scenes=scenes
            )
            
            # 创建时间线 - 兼容 moviepy 1.x 和 2.x
            try:
                from moviepy import VideoFileClip
            except ImportError:
                from moviepy.editor import VideoFileClip
            
            with VideoFileClip(processed_video) as video:
                video_duration = video.duration
            
            timeline = self.smart_clipper.create_timeline(matched_segments, video_duration)
            
            # 如果时间线为空，创建默认时间线
            if not timeline:
                print("   [WARNING] 时间线为空，创建默认片段")
                # 默认取视频的几个关键位置
                default_positions = [
                    (video_duration * 0.05, video_duration * 0.1),   # 开头
                    (video_duration * 0.25, video_duration * 0.35),  # 前半
                    (video_duration * 0.5, video_duration * 0.6),    # 中间
                    (video_duration * 0.7, video_duration * 0.8),    # 高潮
                    (video_duration * 0.9, video_duration * 0.95),   # 结尾
                ]
                for i, (start, end) in enumerate(default_positions):
                    timeline.append({
                        'clip_id': i + 1,
                        'segment_id': i + 1,
                        'phase': f'段落{i+1}',
                        'source_start': start,
                        'source_end': end,
                        'narration_start': 0,
                        'narration_end': end - start,
                        'keep_original': False,
                    })
            
            self.smart_clipper.print_timeline(timeline)
            
            # ========== Step 6: 智能剪辑 ==========
            report_progress(6, "正在精确剪辑视频素材...")
            
            # 提取片段
            clips_to_extract = [
                {
                    'start': item['source_start'],
                    'end': item['source_end']
                }
                for item in timeline
            ]
            
            clips_dir = work_dir / "clips"
            clips_dir.mkdir(exist_ok=True)
            
            clip_files = extract_clips(processed_video, clips_to_extract, str(clips_dir))
            print(f"   ✓ 提取了 {len(clip_files)} 个片段")
            
            # 如果没有提取到片段，使用原视频
            if not clip_files:
                print("   [WARNING] 未提取到片段，使用原视频")
                concat_path = processed_video
            else:
                # 拼接
                concat_path = str(work_dir / "剪辑后.mp4")
                concat_clips(clip_files, concat_path)
            
            # ========== Step 7: 语音合成 ==========
            report_progress(7, "正在生成解说配音...")
            
            # 提取纯文本
            full_narration = '\n'.join([
                seg.get('narration_text', '')
                for seg in matched_segments
            ])
            
            narration_path = str(work_dir / "narration.wav")
            await self.tts_engine.synthesize(full_narration, narration_path)
            print(f"   ✓ 配音已生成: {narration_path}")
            
            # ========== Step 8: 合成输出 ==========
            report_progress(8, "正在合成最终视频...")
            
            # 计算保留原声的片段
            keep_original_segments = [
                (item['source_start'], item['source_end'])
                for item in timeline
                if item.get('keep_original')
            ]
            
            # 合成
            final_path = str(work_dir / f"{output_name}.mp4")
            compose_final_video(
                video_path=concat_path,
                narration_path=narration_path,
                output_path=final_path,
                keep_original_segments=keep_original_segments,
                mode="mix"
            )
            
            # 添加字幕
            subtitle_path = str(work_dir / "subtitles.srt")
            self._generate_subtitles(matched_segments, subtitle_path)
            
            final_with_sub = str(work_dir / f"{output_name}_sub.mp4")
            add_subtitles(final_path, subtitle_path, final_with_sub)
            
            # 转抖音格式
            douyin_path = str(work_dir / f"{output_name}_抖音.mp4")
            convert_to_douyin(final_with_sub, douyin_path)
            
            # 完成
            elapsed = (datetime.now() - start_time).seconds
            self._print_footer(final_path, elapsed)
            
            return {
                'video_path': final_path,
                'douyin_path': douyin_path,
                'script_path': str(script_path),
                'subtitle_path': subtitle_path,
                'work_dir': str(work_dir),
                'timeline': timeline,
            }
            
        except Exception as e:
            print(f"\n[ERROR] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _print_header(self, video, name, style, duration):
        """打印开始信息"""
        print("\n" + "★"*60)
        print("★  SmartVideoClipper v3.0 - 解说驱动剪辑")
        print("★  ")
        print("★  核心理念: 先理解故事 → 写解说 → 配画面")
        print("★  " + "="*52)
        print(f"★  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"★  输入视频: {video}")
        print(f"★  作品名称: {name or '未知'}")
        print(f"★  解说风格: {style}")
        print(f"★  目标时长: {duration}秒")
        print("★"*60 + "\n")
    
    def _print_footer(self, output, elapsed):
        """打印完成信息"""
        minutes = elapsed // 60
        seconds = elapsed % 60
        print("\n" + "★"*60)
        print("★  ✅ 处理完成！")
        print("★  " + "="*52)
        print(f"★  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"★  总耗时: {minutes}分{seconds}秒")
        print(f"★  输出文件: {output}")
        print("★"*60)
    
    def _format_script(self, segments: list) -> str:
        """格式化剧本为文本"""
        lines = []
        lines.append("=" * 50)
        lines.append("SmartVideoClipper v3.0 - 解说剧本")
        lines.append("=" * 50)
        lines.append("")
        
        for seg in segments:
            lines.append(f"【{seg.get('phase', '未知')}】")
            if seg.get('scene_description'):
                lines.append(f"[画面: {seg['scene_description']}]")
            lines.append(seg.get('narration_text', ''))
            lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_subtitles(self, segments: list, output_path: str):
        """生成SRT字幕文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            idx = 1
            time_cursor = 0.0
            
            for seg in segments:
                text = seg.get('narration_text', '')
                duration = seg.get('duration', 30)
                
                # 分句
                sentences = text.replace('。', '。\n').replace('！', '！\n').split('\n')
                
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    
                    # 估算时长
                    sent_duration = max(2, len(sent) / 4)
                    
                    start_time = self._format_srt_time(time_cursor)
                    end_time = self._format_srt_time(time_cursor + sent_duration)
                    
                    f.write(f"{idx}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sent}\n\n")
                    
                    idx += 1
                    time_cursor += sent_duration
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# 便捷函数
async def process_video_v3(
    input_video: str,
    movie_name: str = None,
    output_name: str = "解说视频",
    style: str = "幽默",
    target_duration: int = 300,
    progress_callback: Optional[Callable] = None
) -> dict:
    """
    新版处理入口
    """
    pipeline = VideoPipelineV3()
    return await pipeline.process(
        input_video=input_video,
        movie_name=movie_name,
        output_name=output_name,
        style=style,
        target_duration=target_duration,
        progress_callback=progress_callback
    )


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
        movie_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        asyncio.run(process_video_v3(
            input_video=test_video,
            movie_name=movie_name,
            output_name="测试输出",
            style="幽默",
            target_duration=300
        ))
    else:
        print("用法: python pipeline_v3.py <视频路径> [作品名称]")

