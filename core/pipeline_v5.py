# core/pipeline_v5.py - 智能视频剪辑流水线 v5.0 (已修复版)
"""
SmartVideoClipper v5.0 - 全球第一的智能视频解说

已修复的核心问题：
1. ✅ 音频分段切换（每个片段独立处理，不是全程混音）
2. ✅ TTS分段生成（每个解说场景单独生成音频）
3. ✅ 解说-画面时长对齐
4. ✅ 智能时长控制
5. ✅ 敏感词多层过滤

处理流程：
Step 0: 预处理（去片头片尾）
Step 1: 语音识别（获取对话）
Step 2: 场景分析（标记精彩/过渡）
Step 3: 智能解说（生成文案）
Step 4: 时长控制（选择场景）
Step 5: TTS分段合成
Step 6: 片段处理（原声/解说分开）
Step 7: 输出成品
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "core"))

# 环境配置
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# GPU加速检测
try:
    from gpu_encoder import get_encoder, is_hardware_available
    GPU_ENCODER = get_encoder()
except ImportError:
    GPU_ENCODER = None
    def is_hardware_available():
        return False


PROCESS_STEPS_V5 = {
    0: "预处理",
    1: "语音识别", 
    2: "场景分析",
    3: "智能解说",
    4: "时长控制",
    5: "TTS分段合成",
    6: "片段处理",
    7: "输出成品",
}


class VideoPipelineV5:
    """
    SmartVideoClipper v5.0 处理流水线 (已修复版)
    
    核心改进：
    - 每个片段独立处理音频（不是全程混音）
    - 每个解说场景单独生成TTS
    - 解说时长自动适配场景时长
    - 智能选择场景以达到目标时长
    """
    
    def __init__(self):
        self.start_time = None
        self.work_dir = None
        
    async def process(
        self,
        video_path: str,
        output_name: str,
        title: str = "",
        style: str = "幽默",
        min_duration: int = 180,   # 最短3分钟
        max_duration: int = 900,   # 最长15分钟
        media_type: str = "auto",  # auto/tv/movie
        episode: int = 0,          # 第几集/部（0=自动检测）
        progress_callback=None
    ) -> Dict:
        """
        处理视频
        
        参数：
            video_path: 视频路径
            output_name: 输出名称
            title: 作品名称
            style: 解说风格
            min_duration: 最短时长（秒）
            max_duration: 最长时长（秒）
            media_type: 媒体类型 (auto自动/tv电视剧/movie电影)
            episode: 集数/部数 (0表示自动从文件名解析)
            progress_callback: 进度回调
        """
        self.start_time = datetime.now()
        
        # 创建工作目录
        self.work_dir = project_root / f"workspace_{output_name}"
        self.work_dir.mkdir(exist_ok=True)
        
        def report_progress(step: int, message: str):
            """报告进度"""
            elapsed = (datetime.now() - self.start_time).seconds
            pct = int(step / 8 * 100)
            
            print(f"\n{'='*60}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 进度: {'█'*(pct//3)}{'░'*(33-pct//3)} {pct}%")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 步骤 {step}/8: {PROCESS_STEPS_V5.get(step, '未知')}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 已耗时: {elapsed}秒")
            print(f"{'='*60}")
            
            if progress_callback:
                progress_callback(step, message, pct)
        
        # 自动检测媒体类型和集数
        from plot_fetcher import parse_episode_from_filename, extract_title_from_filename
        
        if not title:
            title = extract_title_from_filename(video_path)
        
        # 自动解析集数
        auto_season, auto_episode = parse_episode_from_filename(video_path)
        if episode == 0:
            episode = auto_episode
        
        # 自动判断媒体类型（有集数标记 → 电视剧）
        if media_type == "auto":
            if auto_episode > 1 or "E0" in video_path.upper() or "第" in video_path and "集" in video_path:
                media_type = "tv"
            else:
                media_type = "movie"  # 默认电影
        
        # 打印启动信息
        print("\n" + "="*60)
        print("[PIPELINE] SmartVideoClipper v5.1 - 电影/电视剧分离版")
        print("="*60)
        print("   核心升级:")
        print("   1. [OK] 电影/电视剧模式分离（解说策略不同）")
        print("   2. [OK] 音频分段切换（每个片段独立处理）")
        print("   3. [OK] TTS分段生成（解说-画面精确对齐）")
        print("   4. [OK] 智能时长控制")
        print("   5. [OK] GPU硬件加速编码")
        print("="*60)
        
        # GPU加速状态
        if GPU_ENCODER:
            gpu_info = GPU_ENCODER.get_info()
            if gpu_info['is_hardware']:
                print(f"   [GPU] 加速: {gpu_info['name']} (10x速提升!)")
            else:
                print(f"   [GPU] 不可用，使用CPU编码")
        else:
            print(f"   [GPU] 检测模块未加载")
        
        print("="*60)
        print(f"   开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   输入视频: {video_path}")
        print(f"   作品名称: {title}")
        media_type_cn = "电视剧" if media_type == "tv" else "电影"
        print(f"   媒体类型: {media_type_cn}")
        if media_type == "tv":
            print(f"   当前集数: 第{episode}集")
            print(f"   解说策略: 讲述本集故事（60%解说+40%原声）")
        else:
            print(f"   当前部数: 第{episode}部")
            print(f"   解说策略: 精彩片段集锦（40%解说+60%原声）")
        print(f"   解说风格: {style}")
        print(f"   时长范围: {min_duration//60}-{max_duration//60}分钟")
        print("="*60 + "\n")
        
        try:
            # ========== Step 0: 预处理 ==========
            report_progress(0, "检测并去除片头片尾...")
            
            from intro_outro_detect import auto_trim_intro_outro
            # 返回值: (输出路径, 片头结束时间, 片尾开始时间)
            trim_result = auto_trim_intro_outro(video_path, str(self.work_dir))
            
            if isinstance(trim_result, tuple):
                processed_video = trim_result[0]
            else:
                processed_video = trim_result
            
            if not processed_video or not os.path.exists(processed_video):
                processed_video = video_path
                print("   [INFO] 无需裁剪，使用原视频")
            
            # ========== Step 1: 语音识别 ==========
            report_progress(1, "识别视频中的对话...")
            
            from transcribe import transcribe_video
            srt_path = str(self.work_dir / "subtitles.srt")
            segments, full_text = transcribe_video(processed_video, output_srt=srt_path)
            
            print(f"   ✓ 识别到 {len(segments)} 段对话")
            
            # ========== Step 2: 场景分析 ==========
            report_progress(2, "分析视频场景...")
            
            from scene_detect import detect_scenes
            from smart_importance import calculate_scene_importance
            from plot_fetcher import PlotFetcher
            
            # 获取剧情信息（电视剧：获取分集剧情）
            plot_fetcher = PlotFetcher()
            plot_info = plot_fetcher.fetch(
                title=title,
                media_type=media_type,
                season=auto_season,
                episode=episode
            )
            plot_fetcher.close()
            
            # 提取分集剧情（用于解说引擎）
            episode_plot = ""
            if media_type == "tv":
                episode_plot = plot_info.get('episode_overview', '') or plot_info.get('overview', '')
                if episode_plot:
                    print(f"   [剧情] 第{episode}集剧情: {episode_plot[:80]}...")
                else:
                    # 使用AI从字幕总结本集剧情
                    from plot_fetcher import summarize_plot_from_transcript
                    episode_plot = summarize_plot_from_transcript(full_text, segments)
                    if episode_plot:
                        print(f"   [剧情] AI总结本集剧情: {episode_plot[:80]}...")
            
            # 检测场景
            scenes_dir = str(self.work_dir / "scenes")
            raw_scenes, _ = detect_scenes(processed_video, scenes_dir)  # 解包元组
            print(f"   检测到 {len(raw_scenes)} 个场景")
            
            # 计算重要性并关联对话
            analyzed_scenes = []
            for i, scene in enumerate(raw_scenes):
                scene_start = scene['start']  # 修正键名
                scene_end = scene['end']      # 修正键名
                
                # 找到该场景内的对话
                scene_dialogue = ""
                for seg in segments:
                    if seg['start'] >= scene_start and seg['end'] <= scene_end:
                        scene_dialogue += seg['text'] + " "
                    elif seg['start'] < scene_end and seg['end'] > scene_start:
                        scene_dialogue += seg['text'] + " "
                
                scene_dialogue = scene_dialogue.strip()
                
                # 检测情感
                emotion = self._detect_emotion(scene_dialogue)
                
                # 计算重要性
                importance = calculate_scene_importance(
                    scene_dialogue, 
                    scene_end - scene_start,
                    emotion
                )
                
                analyzed_scenes.append({
                    'scene_id': i + 1,
                    'start_time': scene_start,
                    'end_time': scene_end,
                    'dialogue': scene_dialogue,
                    'emotion': emotion,
                    'importance': importance,
                })
            
            print(f"   ✓ 场景分析完成")
            
            # ========== Step 3: 智能解说 ==========
            report_progress(3, f"生成{style}风格解说（{media_type_cn}模式）...")
            
            from narration_engine import NarrationEngine
            
            # 初始化解说引擎（传入媒体类型和集数）
            engine = NarrationEngine(
                use_ai=True, 
                media_type=media_type, 
                episode=episode
            )
            scene_segments, narration_text = engine.analyze_and_generate(
                analyzed_scenes, 
                title, 
                style,
                episode_plot=episode_plot  # 传入分集剧情
            )
            
            # 转换为字典格式
            scenes_with_narration = []
            for seg in scene_segments:
                scenes_with_narration.append({
                    'scene_id': seg.scene_id,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time,
                    'dialogue': seg.dialogue,
                    'narration': seg.narration,
                    'audio_mode': seg.audio_mode.value,  # 转为字符串
                    'importance': seg.importance,
                    'emotion': seg.emotion,
                    'reason': seg.reason,
                })
            
            print(f"   ✓ 解说生成完成")
            
            # ========== Step 4: 时长控制 ==========
            report_progress(4, "智能选择场景...")
            
            from duration_controller import DurationController
            
            controller = DurationController(
                min_duration=min_duration,
                max_duration=max_duration,
                original_ratio=0.3  # 至少30%原声
            )
            
            timeline = controller.create_optimized_timeline(
                scenes_with_narration,
                target_duration=None  # 自动计算
            )
            
            # 过滤跳过的场景
            active_timeline = [t for t in timeline if t['audio_mode'] != 'skip']
            
            if not active_timeline:
                raise ValueError("没有可用的场景")
            
            total_duration = sum(t['duration'] for t in active_timeline)
            
            print(f"   ✓ 选择了 {len(active_timeline)} 个场景")
            print(f"   预计时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
            
            # 保存解说剧本
            script_path = self.work_dir / "解说剧本_v5.txt"
            self._save_script(active_timeline, script_path, title, style)
            
            # ========== Step 5: TTS分段合成 ==========
            report_progress(5, "分段合成解说配音...")
            
            from tts_segmented import synthesize_timeline_narrations
            
            tts_dir = self.work_dir / "tts"
            narration_segments = await synthesize_timeline_narrations(
                active_timeline,
                str(tts_dir)
            )
            
            print(f"   ✓ 生成 {len(narration_segments)} 个解说音频")
            
            # ========== Step 6: 片段处理 ==========
            report_progress(6, "处理视频片段（原声/解说分开）...")
            
            from clip_processor import process_timeline_clips, concat_processed_clips
            
            clips_dir = self.work_dir / "clips"
            
            # 处理每个片段（关键改进：每个片段独立处理音频）
            clip_files, clips_duration = process_timeline_clips(
                source_video=processed_video,
                timeline=active_timeline,
                narration_segments=narration_segments,
                output_dir=str(clips_dir)
            )
            
            # 拼接所有片段
            output_video = str(self.work_dir / f"{output_name}.mp4")
            
            if not clip_files:
                raise ValueError("没有成功提取任何视频片段")
            
            concat_success = concat_processed_clips(clip_files, output_video)
            if not concat_success:
                raise RuntimeError("视频片段拼接失败")
            
            print(f"   ✓ 视频处理完成")
            
            # ========== Step 7: 输出成品 ==========
            report_progress(7, "生成最终成品...")
            
            from audio_composer import add_subtitles, convert_to_vertical
            
            # 添加字幕
            output_with_sub = str(self.work_dir / f"{output_name}_sub.mp4")
            add_subtitles(output_video, srt_path, output_with_sub)
            
            # 生成抖音版
            output_douyin = str(self.work_dir / f"{output_name}_抖音.mp4")
            convert_to_vertical(output_video, output_douyin)
            
            # 完成
            end_time = datetime.now()
            elapsed = (end_time - self.start_time).seconds
            
            print("\n" + "★"*60)
            print("★  ✅ v5.0 处理完成！")
            print("★  ====================================================")
            print(f"★  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"★  总耗时: {elapsed//60}分{elapsed%60}秒")
            print(f"★  输出文件: {output_video}")
            print("★"*60 + "\n")
            
            # 统计
            orig_count = sum(1 for t in active_timeline if t['audio_mode'] == 'original')
            voice_count = sum(1 for t in active_timeline if t['audio_mode'] == 'voiceover')
            
            return {
                'success': True,
                'output_video': output_video,
                'output_douyin': output_douyin,
                'output_with_subtitle': output_with_sub,
                'script_path': str(script_path),
                'subtitle_path': srt_path,
                'duration': total_duration,
                'original_scenes': orig_count,
                'voiceover_scenes': voice_count,
                'work_dir': str(self.work_dir),
            }
            
        except Exception as e:
            print(f"\n[ERROR] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
            }
    
    def _detect_emotion(self, dialogue: str) -> str:
        """检测对话情感"""
        if not dialogue:
            return 'neutral'
        
        emotion_keywords = {
            'angry': ['滚', '混蛋', '妈的', '操', '杀', '打', '揍', '愤怒', '生气', '去死'],
            'sad': ['哭', '泪', '难过', '伤心', '痛苦', '对不起', '抱歉', '悲伤', '死了'],
            'happy': ['哈哈', '开心', '高兴', '太好了', '棒', '赞', '笑', '哈'],
            'fear': ['怕', '害怕', '恐惧', '可怕', '吓', '惊', '救命'],
            'excited': ['激动', '兴奋', '太棒了', '不敢相信', '天哪'],
        }
        
        for emotion, keywords in emotion_keywords.items():
            if any(kw in dialogue for kw in keywords):
                return emotion
        
        return 'neutral'
    
    def _save_script(self, timeline: List[Dict], path: Path, title: str, style: str):
        """保存解说剧本"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"SmartVideoClipper v5.0 - 解说剧本 (已修复版)")
        lines.append(f"作品: {title}")
        lines.append(f"风格: {style}")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append("")
        lines.append("核心改进：")
        lines.append("  1. 每个片段独立处理音频（原声/解说分开）")
        lines.append("  2. TTS分段生成（解说-画面精确对齐）")
        lines.append("  3. 智能时长控制")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        
        for i, item in enumerate(timeline, 1):
            mode = "🔊原声" if item['audio_mode'] == 'original' else "🎙️解说"
            lines.append(f"【场景 {i}】 {mode}")
            lines.append(f"时间: {item['source_start']:.1f}s - {item['source_end']:.1f}s ({item['duration']:.1f}秒)")
            lines.append(f"重要性: {item['importance']:.2f}")
            
            if item.get('dialogue'):
                lines.append(f"对白: {item['dialogue'][:100]}...")
            
            if item.get('narration') and item['audio_mode'] == 'voiceover':
                lines.append(f"解说: {item['narration']}")
            
            if item.get('reason'):
                lines.append(f"原因: {item['reason']}")
            
            lines.append("")
        
        # 统计
        orig_count = sum(1 for t in timeline if t['audio_mode'] == 'original')
        voice_count = sum(1 for t in timeline if t['audio_mode'] == 'voiceover')
        total_duration = sum(t['duration'] for t in timeline)
        
        lines.append("=" * 60)
        lines.append("统计:")
        lines.append(f"  总场景: {len(timeline)}")
        lines.append(f"  原声场景: {orig_count} ({orig_count*100//(orig_count+voice_count+1)}%)")
        lines.append(f"  解说场景: {voice_count} ({voice_count*100//(orig_count+voice_count+1)}%)")
        lines.append(f"  总时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
        lines.append("=" * 60)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"   ✓ 剧本已保存: {path}")


async def run_v5(
    video_path: str,
    output_name: str,
    title: str = "",
    style: str = "幽默",
    min_duration: int = 180,
    max_duration: int = 900,
    media_type: str = "auto",  # 🆕 媒体类型 (auto/tv/movie)
    episode: int = 0           # 🆕 集数/部数
) -> Dict:
    """
    运行 v5.1 流水线
    
    这是对外的主入口
    
    参数：
        video_path: 视频路径
        output_name: 输出名称
        title: 作品名称
        style: 解说风格
        min_duration: 最短时长（秒）
        max_duration: 最长时长（秒）
        media_type: 媒体类型 (auto自动/tv电视剧/movie电影)
        episode: 集数/部数（0=自动从文件名解析）
    """
    pipeline = VideoPipelineV5()
    return await pipeline.process(
        video_path=video_path,
        output_name=output_name,
        title=title,
        style=style,
        min_duration=min_duration,
        max_duration=max_duration,
        media_type=media_type,
        episode=episode
    )


# 测试入口
if __name__ == "__main__":
    import asyncio
    
    async def test():
        result = await run_v5(
            video_path=r"C:\Users\Administrator\Downloads\狂飙E01.mp4",
            output_name="狂飙第一集_v5",
            title="狂飙",
            style="幽默"
        )
        print(result)
    
    asyncio.run(test())
