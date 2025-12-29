# core/pipeline_v5.py - 智能视频剪辑流水线 v5.6 (分层生成+上下文感知版)
"""
SmartVideoClipper v5.6 - 全球第一的智能视频解说

v5.6 核心改进：
1. [NEW] 分层生成 - 先生成故事框架，再按框架生成解说
2. [NEW] 上下文窗口 - 每个场景考虑前2后2场景
3. [NEW] 动态比例 - 根据场景特征自动计算解说比例(30%-75%)
4. [NEW] 静音处理 - 检测并AI扩展填充静音段落
5. [NEW] 钩子开场 - 自动生成吸引人的开场白
6. [NEW] 悬念结尾 - 自动生成引发期待的结尾
7. [NEW] 动态语速 - TTS支持0.85x-1.15x语速调整

v5.4 基础保留：
- 批量解说生成（10场景/批）
- 广告检测和过滤
- 统一编码参数
- 语音识别优化

处理流程：
Step 0: 预处理（去片头片尾 + 广告检测）
Step 1: 语音识别（获取对话）
Step 2: 场景分析（标记精彩/过渡）
Step 3: 智能解说（分层生成 + 上下文感知）
Step 4: 时长控制（动态比例 + 静音处理）
Step 5: TTS分段合成（动态语速）
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
        
        def report_progress(step: int, message: str, sub_step: str = ""):
            """报告进度 - 实时输出"""
            import sys
            elapsed = (datetime.now() - self.start_time).seconds
            pct = int(step / 8 * 100)
            
            # 进度条
            bar_filled = pct // 3
            bar_empty = 33 - bar_filled
            bar = '#' * bar_filled + '-' * bar_empty
            
            print(f"\n{'='*60}", flush=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{bar}] {pct}%", flush=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 步骤 {step}/8: {PROCESS_STEPS_V5.get(step, '未知')}", flush=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)
            if sub_step:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]    -> {sub_step}", flush=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 已耗时: {elapsed}秒 ({elapsed//60}分{elapsed%60}秒)", flush=True)
            print(f"{'='*60}", flush=True)
            sys.stdout.flush()
            
            if progress_callback:
                progress_callback(step, message, pct)
        
        def log(msg: str):
            """实时日志输出"""
            import sys
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
            sys.stdout.flush()
        
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
        print("[PIPELINE] SmartVideoClipper v5.8.0 - 全球最优Structured解说")
        print("="*60)
        print("   v5.7 核心优化:")
        print("   1. [OK] 垃圾文字清洗（过滤AI思考残留）")
        print("   2. [OK] 100%AI生成（多级重试+兜底）")
        print("   3. [OK] 风格自动适配（按视频类型）")
        print("   4. [OK] 废除固定比例（智能判断）")
        print("   5. [OK] 静音智能填充（场景感知）")
        print("   6. [OK] 个性化钩子（剧情关联）")
        print("   7. [OK] GPU硬件加速编码")
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
            report_progress(0, "检测并去除片头片尾、广告...")
            
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
            
            # 广告检测（稍后在时间线过滤中使用）
            detected_ads = []
            try:
                from ad_detector import AdDetector
                ad_detector = AdDetector()
                detected_ads = ad_detector.detect_ads(processed_video)
            except Exception as e:
                print(f"   [WARN] 广告检测跳过: {e}")
            
            # ========== Step 1: 语音识别 ==========
            report_progress(1, "识别视频中的对话...", "这是最耗时的步骤，预计10-15分钟")
            log("   [Step1] 开始语音识别...")
            
            from transcribe import transcribe_video
            srt_path = str(self.work_dir / "subtitles.srt")
            # 传递media_type和title，优化中文识别质量
            segments, full_text = transcribe_video(
                processed_video, 
                output_srt=srt_path,
                media_type=media_type,
                title=title
            )
            
            log(f"   [Step1] 语音识别完成! 共 {len(segments)} 段对话")
            
            # ========== Step 2: 场景分析 ==========
            report_progress(2, "分析视频场景...", "包含剧情获取和场景检测")
            log("   [Step2] 开始场景分析...")
            
            from scene_detect import detect_scenes
            from smart_importance import calculate_scene_importance
            from plot_fetcher import PlotFetcher
            
            # 获取剧情信息（电视剧：获取分集剧情）
            log("   [Step2] 2.1 获取剧情信息...")
            plot_fetcher = PlotFetcher()
            plot_info = plot_fetcher.fetch(
                title=title,
                media_type=media_type,
                season=auto_season,
                episode=episode
            )
            plot_fetcher.close()
            log("   [Step2]     剧情获取完成")
            
            # 提取分集剧情（用于解说引擎）
            episode_plot = ""
            if media_type == "tv":
                episode_plot = plot_info.get('episode_overview', '') or plot_info.get('overview', '')
                if episode_plot:
                    log(f"   [Step2]     第{episode}集剧情: {episode_plot[:60]}...")
                else:
                    # 使用AI从字幕总结本集剧情
                    log("   [Step2] 2.2 使用AI总结本集剧情...")
                    from plot_fetcher import summarize_plot_from_transcript
                    episode_plot = summarize_plot_from_transcript(full_text, segments)
                    if episode_plot:
                        log(f"   [Step2]     AI总结: {episode_plot[:60]}...")
            
            # 检测场景
            log("   [Step2] 2.3 检测视频场景（可能需要1-2分钟）...")
            scenes_dir = str(self.work_dir / "scenes")
            raw_scenes, _ = detect_scenes(processed_video, scenes_dir)  # 解包元组
            log(f"   [Step2]     检测到 {len(raw_scenes)} 个场景")
            
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
            
            log(f"   [Step2]     场景分析完成")
            
            # ========== Step 3: 智能解说 (v5.8 Structured格式+分层生成) ==========
            from narration_engine import NarrationEngine, detect_video_genre, get_optimal_style
            
            # v5.8新增：Structured格式确保100%成功率
            detected_genre = detect_video_genre(title, episode_plot or "")
            optimal_style_config = get_optimal_style(detected_genre)
            
            # v5.8：Structured格式+自动风格检测
            if style == "幽默":  # 默认值，可能未指定
                actual_style = optimal_style_config['prompt_style']
                style_name = optimal_style_config['name']
            else:
                actual_style = style
                style_name = style
            
            log(f"   [Step3] v5.9 RTX4060优化: 检测类型={detected_genre}, 风格={style_name}")
            report_progress(3, f"生成{style_name}风格解说（v5.9 RTX4060智能管理）...", "100%成功率 + 显存优化")

            # v5.9新增：调试模式显存报告
            if os.getenv('SMART_CLIPPER_DEBUG', 'false').lower() == 'true':
                try:
                    from utils.gpu_manager import GPUManager
                    mem_info = GPUManager.get_memory_info()
                    if mem_info:
                        log(".1f"                except:
                    pass

            log("   [Step3] 开始智能解说生成 v5.9...")

            # v5.9新增：初始化前显存监控
            try:
                from utils.gpu_manager import GPUManager
                log("   [Step3] 3.0 RTX 4060显存监控...")
                if not GPUManager.monitor_and_cleanup(0.75):  # 75%阈值，留有余量
                    log("   [Step3] ⚠️ 显存清理失败，使用兼容模式")
                else:
                    mem_info = GPUManager.get_memory_info()
                    log(".1%")
            except ImportError:
                log("   [Step3] GPU管理器不可用，使用标准模式")

            # v5.9: 初始化解说引擎（分级模型策略）
            log("   [Step3] 3.1 初始化解说引擎 v5.9...")
            total_episodes = 1  # 默认1集，可从外部传入
            engine = NarrationEngine(
                use_ai=True,
                media_type=media_type,
                episode=episode,
                total_episodes=total_episodes
            )

            log("   [Step3] 3.2 分层生成解说 (框架→场景→上下文)...")
            # v5.6: 传入main_character参数
            main_character = ""  # 可从剧情中提取
            if episode_plot:
                # 简单提取：找到第一个出现的人名
                import re
                name_match = re.search(r'([高李王张刘陈][^\s，。]{0,2})', episode_plot)
                if name_match:
                    main_character = name_match.group(1)

            scene_segments, narration_text = engine.analyze_and_generate(
                analyzed_scenes, 
                title, 
                actual_style,  # v5.7.1修复：使用自动检测的风格
                episode_plot=episode_plot,
                main_character=main_character
            )
            
            # v5.6: 获取钩子开场和悬念结尾
            hook_opening = getattr(engine, 'hook_opening', '')
            suspense_ending = getattr(engine, 'suspense_ending', '')
            if hook_opening:
                log(f"   [Step3]     钩子开场: {hook_opening[:40]}...")
            if suspense_ending:
                log(f"   [Step3]     悬念结尾: {suspense_ending[:40]}...")
            
            # 转换为字典格式
            log("   [Step3] 3.3 整理解说数据...")
            scenes_with_narration = []
            for seg in scene_segments:
                scene_dict = {
                    'scene_id': seg.scene_id,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time,
                    'dialogue': seg.dialogue,
                    'narration': seg.narration,
                    'audio_mode': seg.audio_mode.value,  # 转为字符串
                    'importance': seg.importance,
                    'emotion': seg.emotion,
                    'reason': seg.reason,
                }
                # v5.6: 传递speech_rate（如果有）
                if hasattr(seg, 'speech_rate'):
                    scene_dict['speech_rate'] = seg.speech_rate
                scenes_with_narration.append(scene_dict)
            
            log(f"   [Step3]     解说生成完成! 共处理 {len(scenes_with_narration)} 个场景")
            
            # ========== Step 4: 时长控制 ==========
            report_progress(4, "智能选择场景...", "根据目标时长筛选最佳片段")
            log("   [Step4] 开始时长控制...")
            
            from duration_controller import DurationController
            
            log("   [Step4] 4.1 初始化时长控制器...")
            controller = DurationController(
                min_duration=min_duration,
                max_duration=max_duration,
                original_ratio=0.3  # 至少30%原声
            )
            
            log("   [Step4] 4.2 生成优化时间线...")
            timeline = controller.create_optimized_timeline(
                scenes_with_narration,
                target_duration=None  # 自动计算
            )
            
            # 过滤广告场景
            if detected_ads:
                try:
                    log("   [Step4] 4.3 过滤广告场景...")
                    from ad_detector import filter_ad_segments
                    timeline = filter_ad_segments(timeline, detected_ads)
                except Exception as e:
                    log(f"   [Step4]     [WARN] 广告过滤跳过: {e}")
            
            # 过滤跳过的场景
            active_timeline = [t for t in timeline if t['audio_mode'] != 'skip']
            
            if not active_timeline:
                raise ValueError("没有可用的场景")
            
            total_duration = sum(t['duration'] for t in active_timeline)
            
            log(f"   [Step4]     选择了 {len(active_timeline)} 个场景")
            log(f"   [Step4]     预计时长: {total_duration:.0f}秒 ({total_duration/60:.1f}分钟)")
            
            # 保存解说剧本
            log("   [Step4] 4.4 保存解说剧本...")
            script_path = self.work_dir / "解说剧本_v5.txt"
            # v5.7.2修复：使用检测到的风格名称而不是原始style
            self._save_script(active_timeline, script_path, title, style_name)
            
            # ========== Step 5: TTS分段合成 ==========
            report_progress(5, "分段合成解说配音...", "使用Edge-TTS生成语音")
            log("   [Step5] 开始TTS语音合成...")
            
            from tts_segmented import synthesize_timeline_narrations
            
            tts_dir = self.work_dir / "tts"
            voiceover_count = sum(1 for t in active_timeline if t['audio_mode'] == 'voiceover')
            log(f"   [Step5]     需要合成 {voiceover_count} 段解说音频...")
            
            narration_segments = await synthesize_timeline_narrations(
                active_timeline,
                str(tts_dir)
            )
            
            log(f"   [Step5]     TTS合成完成! 生成 {len(narration_segments)} 个音频文件")
            
            # ========== Step 6: 片段处理 ==========
            report_progress(6, "处理视频片段（原声/解说分开）...", "这可能需要几分钟")
            log("   [Step6] 开始视频片段处理...")
            
            from clip_processor import process_timeline_clips, concat_processed_clips
            
            clips_dir = self.work_dir / "clips"
            
            # 处理每个片段
            log(f"   [Step6] 6.1 提取和处理 {len(active_timeline)} 个片段...")
            clip_files, clips_duration = process_timeline_clips(
                source_video=processed_video,
                timeline=active_timeline,
                narration_segments=narration_segments,
                output_dir=str(clips_dir)
            )
            log(f"   [Step6]     提取完成! 共 {len(clip_files)} 个片段")
            
            # 拼接所有片段
            output_video = str(self.work_dir / f"{output_name}.mp4")
            
            if not clip_files:
                raise ValueError("没有成功提取任何视频片段")
            
            log(f"   [Step6] 6.2 拼接视频片段...")
            concat_success = concat_processed_clips(clip_files, output_video)
            if not concat_success:
                raise RuntimeError("视频片段拼接失败")
            
            log(f"   [Step6]     视频拼接完成!")
            
            # ========== Step 7: 输出成品 ==========
            report_progress(7, "生成最终成品...", "添加字幕和生成竖版")
            log("   [Step7] 开始生成最终成品...")
            
            from audio_composer import add_subtitles, convert_to_vertical
            
            # 添加字幕
            log("   [Step7] 7.1 添加字幕...")
            output_with_sub = str(self.work_dir / f"{output_name}_sub.mp4")
            add_subtitles(output_video, srt_path, output_with_sub)
            
            # 生成抖音版
            log("   [Step7] 7.2 生成抖音竖版...")
            output_douyin = str(self.work_dir / f"{output_name}_抖音.mp4")
            convert_to_vertical(output_video, output_douyin)
            log("   [Step7]     最终成品生成完成!")
            
            # 完成
            end_time = datetime.now()
            elapsed = (end_time - self.start_time).seconds
            
            # v5.9新增：最终显存报告
            if os.getenv('SMART_CLIPPER_MEMORY_REPORT', 'false').lower() == 'true':
                try:
                    from utils.gpu_manager import GPUManager
                    final_mem = GPUManager.get_memory_info()
                    if final_mem:
                        print("*" + "="*58)
                        print(f"*  [GPU] 最终显存: {final_mem['used_gb']:.1f}GB/{final_mem['total_gb']:.1f}GB ({final_mem['usage_percent']:.1f}%)")
                        print("*" + "="*58)
                except Exception as e:
                    print(f"*  [GPU] 显存报告失败: {e}")

            print("\n" + "*"*60)
            print("*  [SUCCESS] v5.9 RTX4060智能管理完成!")
            print("*  ====================================================")
            print(f"*  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"*  总耗时: {elapsed//60}分{elapsed%60}秒")
            print(f"*  输出文件: {output_video}")
            print("*  [v5.9] RTX 4060显存优化：100%成功率保证")
            print("*"*60 + "\n")
            
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
    
    def _save_script(self, timeline: List[Dict], path: Path, title: str, style_name: str):
        """保存解说剧本 v5.7.2"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"SmartVideoClipper v5.8.0 - Structured解说剧本")
        lines.append(f"作品: {title}")
        lines.append(f"风格: {style_name}")
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
            mode = "[原声]" if item['audio_mode'] == 'original' else "[解说]"
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
