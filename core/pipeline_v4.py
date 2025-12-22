# core/pipeline_v4.py - 第四代处理管线
"""
SmartVideoClipper v4.0 - 基于视频内容的解说生成

核心改进：
1. 看画面写解说（不是写解说找画面）
2. 解说和原声二选一（不混合）
3. 画面-解说精确对齐
4. TMDB API 获取详细剧情

真正做到：全球第一的智能视频解说
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime
import json

# 设置环境
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

# 导入模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

from intro_outro_detect import auto_trim_intro_outro
from scene_detect import detect_scenes
from transcribe import transcribe_video
from tts_synthesis import TTSEngine
from smart_cut import extract_clips, concat_clips
from compose_video import compose_v4, add_subtitles, convert_to_douyin
from plot_fetcher import PlotFetcher, get_plot_info, parse_episode_from_filename
from video_content_analyzer import VideoContentAnalyzer, create_scene_based_timeline


# 处理步骤
PROCESS_STEPS_V4 = [
    (0, "预处理", "检测并去除片头片尾"),
    (1, "剧情获取", "TMDB API获取详细剧情"),
    (2, "语音识别", "识别视频对白"),
    (3, "场景分析", "分析每个场景的内容"),
    (4, "生成解说", "基于画面内容写解说"),
    (5, "素材剪辑", "精确剪辑视频素材"),
    (6, "语音合成", "生成解说配音"),
    (7, "合成输出", "解说/原声分离合成"),
]
TOTAL_STEPS_V4 = len(PROCESS_STEPS_V4)


class VideoPipelineV4:
    """
    第四代视频处理管线
    
    核心理念：看画面写解说
    """
    
    def __init__(self):
        self.content_analyzer = VideoContentAnalyzer()
        self.tts_engine = TTSEngine()
    
    async def process(
        self,
        input_video: str,
        movie_name: str = None,
        output_name: str = "解说视频",
        style: str = "幽默",
        target_duration: int = 600,
        progress_callback: Optional[Callable] = None,
        tmdb_api_key: str = None
    ) -> dict:
        """
        执行完整处理流程
        """
        start_time = datetime.now()
        
        # 创建工作目录
        work_dir = Path(f"workspace_{output_name}_v4")
        work_dir.mkdir(exist_ok=True)
        
        def report_progress(step: int, detail: str):
            if progress_callback:
                step_name = PROCESS_STEPS_V4[step][1] if step < len(PROCESS_STEPS_V4) else "完成"
                progress_callback(step, TOTAL_STEPS_V4, step_name, detail)
            print(f"\n[Step {step}] {detail}")
        
        # 打印头部
        self._print_header(input_video, movie_name, style, target_duration)
        
        try:
            # ========== Step 0: 预处理 ==========
            report_progress(0, "正在检测片头片尾...")
            
            trimmed_path = str(work_dir / "trimmed_video.mp4")
            processed_video, intro_offset, outro_time = auto_trim_intro_outro(
                input_video, trimmed_path, skip_if_short=300
            )
            if processed_video != input_video:
                print(f"   ✓ 已去除片头: {intro_offset:.1f}秒")
            
            # ========== Step 1: 剧情获取 ==========
            report_progress(1, f"正在获取《{movie_name or '未知'}》的剧情...")
            
            # 使用 TMDB API
            api_key = tmdb_api_key or os.environ.get("TMDB_API_KEY", "")
            season, episode = parse_episode_from_filename(input_video)
            
            plot_info = {}
            if api_key:
                fetcher = PlotFetcher(api_key)
                plot_info = fetcher.fetch(
                    title=movie_name or "未知",
                    media_type="auto",
                    season=season,
                    episode=episode
                )
                fetcher.close()
                
                if plot_info.get('overview'):
                    print(f"   ✓ TMDB获取成功：{len(plot_info['overview'])}字")
            else:
                print("   [INFO] 未配置TMDB API，跳过")
            
            # ========== Step 2: 语音识别 ==========
            report_progress(2, "正在识别视频对白...")
            
            subtitle_path = str(work_dir / "subtitles.srt")
            segments, transcript = transcribe_video(
                processed_video,
                output_srt=subtitle_path
            )
            print(f"   ✓ 识别到 {len(segments)} 段对白")
            
            # ========== Step 3: 场景分析 ==========
            report_progress(3, "正在分析每个场景的内容...")
            
            # 检测场景
            scenes, _ = detect_scenes(processed_video, str(work_dir))
            print(f"   检测到 {len(scenes)} 个场景")
            
            # 分析场景内容
            analyzed_scenes = self.content_analyzer.analyze_video(
                video_path=processed_video,
                scenes=scenes,
                transcript_segments=segments
            )
            
            # 保存分析结果
            with open(work_dir / "scene_analysis.json", 'w', encoding='utf-8') as f:
                # 清理不可序列化的内容
                clean_scenes = []
                for s in analyzed_scenes:
                    clean_scene = {k: v for k, v in s.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
                    clean_scenes.append(clean_scene)
                json.dump(clean_scenes, f, ensure_ascii=False, indent=2)
            
            # ========== Step 4: 生成解说 ==========
            report_progress(4, f"正在为每个场景生成{style}风格解说...")
            
            # 基于场景内容生成解说
            narrated_scenes = self.content_analyzer.generate_scene_narrations(
                analyzed_scenes=analyzed_scenes,
                target_duration=target_duration,
                style=style
            )
            
            # 如果有剧情信息，用AI增强解说
            if plot_info.get('overview'):
                narrated_scenes = await self._enhance_narrations_with_plot(
                    narrated_scenes, plot_info, style
                )
            
            # 保存解说剧本
            script_text = self._format_scene_script(narrated_scenes)
            script_path = work_dir / "解说剧本_v4.txt"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_text)
            print(f"   ✓ 剧本已保存: {script_path}")
            
            # ========== Step 5: 素材剪辑 ==========
            report_progress(5, "正在精确剪辑视频素材...")
            
            # 创建时间线
            timeline = create_scene_based_timeline(narrated_scenes, target_duration)
            
            # 打印时间线
            self._print_timeline(timeline)
            
            # 提取片段
            clips_to_extract = [
                {'start': item['source_start'], 'end': item['source_end']}
                for item in timeline
            ]
            
            clips_dir = work_dir / "clips"
            clips_dir.mkdir(exist_ok=True)
            clip_files = extract_clips(processed_video, clips_to_extract, str(clips_dir))
            print(f"   ✓ 提取了 {len(clip_files)} 个片段")
            
            # 拼接
            concat_path = str(work_dir / "剪辑后.mp4")
            concat_clips(clip_files, concat_path)
            
            # ========== Step 6: 语音合成 ==========
            report_progress(6, "正在生成解说配音...")
            
            # 只为需要解说的场景生成TTS
            voiceover_text = '\n'.join([
                item.get('narration_text', '')
                for item in timeline
                if item.get('audio_mode') == 'voiceover' and item.get('narration_text')
            ])
            
            narration_path = str(work_dir / "narration.wav")
            if voiceover_text.strip():
                await self.tts_engine.synthesize(voiceover_text, narration_path)
                print(f"   ✓ 配音已生成: {narration_path}")
            else:
                # 生成静音音频
                print("   [INFO] 无需解说，生成静音音频")
                self._generate_silence(narration_path, 1.0)
            
            # ========== Step 7: 合成输出 ==========
            report_progress(7, "正在合成最终视频（解说/原声分离）...")
            
            final_path = str(work_dir / f"{output_name}.mp4")
            compose_v4(
                video_clips=clip_files,
                narration_path=narration_path,
                output_path=final_path,
                timeline=timeline
            )
            
            # 添加字幕
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
                'analyzed_scenes': len(analyzed_scenes),
            }
            
        except Exception as e:
            print(f"\n[ERROR] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _enhance_narrations_with_plot(
        self,
        scenes: List[Dict],
        plot_info: Dict,
        style: str
    ) -> List[Dict]:
        """用剧情信息增强解说"""
        try:
            import ollama
            
            # 获取可用模型
            models = ollama.list()
            model = None
            if hasattr(models, 'models'):
                for m in models.models:
                    model = getattr(m, 'name', None)
                    if model:
                        break
            
            if not model:
                return scenes
            
            plot_summary = plot_info.get('overview', '')[:500]
            characters = plot_info.get('cast', [])[:5]
            char_names = [c.get('character', c.get('name', '')) for c in characters]
            
            print(f"   [AI] 使用 {model} 增强解说...")
            
            for scene in scenes:
                if scene.get('narration_type') == 'voiceover' and scene.get('narration'):
                    original_narration = scene['narration']
                    
                    prompt = f"""你是影视解说博主，风格{style}。

剧情背景：{plot_summary}
主要人物：{', '.join(char_names)}

当前画面：{scene.get('visual_content', '')}
当前对话：{scene.get('dialogue', '')[:100]}

原有解说：{original_narration}

请改写这段解说，使其：
1. 更加贴合画面内容
2. 融入剧情背景
3. 语言生动有趣
4. 控制在50字以内

直接输出改写后的解说，不要有任何其他内容："""

                    try:
                        response = ollama.chat(
                            model=model,
                            messages=[{'role': 'user', 'content': prompt}],
                            options={'temperature': 0.7, 'num_predict': 200}
                        )
                        
                        enhanced = response['message']['content'].strip()
                        if enhanced and len(enhanced) < 150:
                            scene['narration'] = enhanced
                    except:
                        pass
            
            return scenes
            
        except Exception as e:
            print(f"   [WARNING] AI增强失败: {e}")
            return scenes
    
    def _format_scene_script(self, scenes: List[Dict]) -> str:
        """格式化场景剧本"""
        lines = []
        lines.append("=" * 50)
        lines.append("SmartVideoClipper v4.0 - 场景解说剧本")
        lines.append("核心：看画面写解说")
        lines.append("=" * 50)
        lines.append("")
        
        for i, scene in enumerate(scenes, 1):
            lines.append(f"【场景 {i}】")
            lines.append(f"时间: {scene.get('start_time', 0):.1f}s - {scene.get('end_time', 0):.1f}s")
            lines.append(f"画面: {scene.get('visual_content', '未知')}")
            lines.append(f"类型: {scene.get('scene_type', '未知')}")
            lines.append(f"音频: {'原声' if scene.get('narration_type') == 'original' else '解说'}")
            
            if scene.get('dialogue'):
                lines.append(f"对白: {scene['dialogue'][:100]}...")
            
            if scene.get('narration'):
                lines.append(f"解说: {scene['narration']}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _print_timeline(self, timeline: List[Dict]):
        """打印时间线"""
        print("\n" + "="*70)
        print("📋 V4.0 剪辑时间线（解说/原声分离）")
        print("="*70)
        print(f"{'#':<4} {'源视频':<20} {'输出时间':<20} {'音频':<10} {'内容':<20}")
        print("-"*70)
        
        for item in timeline[:20]:  # 只显示前20个
            source = f"{item['source_start']:.1f}s - {item['source_end']:.1f}s"
            output = f"{item['output_start']:.1f}s - {item['output_end']:.1f}s"
            audio = "🔊原声" if item['audio_mode'] == 'original' else "🎙️解说"
            content = item.get('visual_content', '')[:18]
            
            print(f"{item['scene_id']:<4} {source:<20} {output:<20} {audio:<10} {content:<20}")
        
        if len(timeline) > 20:
            print(f"... 还有 {len(timeline) - 20} 个场景")
        
        # 统计
        original_count = sum(1 for t in timeline if t['audio_mode'] == 'original')
        voiceover_count = len(timeline) - original_count
        print("="*70)
        print(f"总计: {len(timeline)} 个场景 | 原声: {original_count} | 解说: {voiceover_count}")
        print("="*70)
    
    def _print_header(self, video, name, style, duration):
        """打印开始信息"""
        print("\n" + "★"*60)
        print("★  SmartVideoClipper v4.0 - 看画面写解说")
        print("★  ")
        print("★  核心改进:")
        print("★  1. 基于视频内容生成解说（不是泛泛而谈）")
        print("★  2. 解说和原声二选一（不混合）")
        print("★  3. 画面-解说精确对齐")
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
        print("★  ✅ V4.0 处理完成！")
        print("★  " + "="*52)
        print(f"★  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"★  总耗时: {minutes}分{seconds}秒")
        print(f"★  输出文件: {output}")
        print("★"*60)
    
    def _generate_silence(self, output_path: str, duration: float):
        """生成静音音频"""
        import subprocess
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=stereo',
            '-t', str(duration),
            '-acodec', 'pcm_s16le',
            output_path
        ]
        subprocess.run(cmd, capture_output=True)


# 便捷函数
async def process_video_v4(
    input_video: str,
    movie_name: str = None,
    output_name: str = "解说视频",
    style: str = "幽默",
    target_duration: int = 600,
    progress_callback: Optional[Callable] = None,
    tmdb_api_key: str = None
) -> dict:
    """V4.0 处理入口"""
    pipeline = VideoPipelineV4()
    return await pipeline.process(
        input_video=input_video,
        movie_name=movie_name,
        output_name=output_name,
        style=style,
        target_duration=target_duration,
        progress_callback=progress_callback,
        tmdb_api_key=tmdb_api_key
    )


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_video = sys.argv[1]
        movie_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        asyncio.run(process_video_v4(
            input_video=test_video,
            movie_name=movie_name,
            output_name="测试输出_v4",
            style="幽默",
            target_duration=300
        ))
    else:
        print("用法: python pipeline_v4.py <视频路径> [作品名称]")

