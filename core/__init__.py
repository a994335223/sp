# SmartVideoClipper - 核心处理模块
# 包含视频处理、AI分析、语音合成等核心功能

from .scene_detect import detect_scenes
from .remove_silence import remove_silence
from .transcribe import transcribe_video
from .analyze_frames import CLIPAnalyzer
from .generate_script import generate_narration_script, generate_narration_script_enhanced
from .smart_cut import extract_clips, concat_clips, parse_keep_original_markers, VIDEO_ENCODER, select_best_clips
from .tts_synthesis import TTSEngine
from .compose_video import compose_final_video, convert_to_douyin
from .auto_polish import apply_cinematic_filter
from .movie_info import MovieInfoFetcher
from .auto_detect_highlights import auto_detect_keep_original
from .cover_generator import auto_generate_cover

__all__ = [
    'detect_scenes',
    'remove_silence',
    'transcribe_video',
    'CLIPAnalyzer',
    'generate_narration_script',
    'generate_narration_script_enhanced',
    'extract_clips',
    'concat_clips',
    'parse_keep_original_markers',
    'VIDEO_ENCODER',
    'select_best_clips',
    'TTSEngine',
    'compose_final_video',
    'convert_to_douyin',
    'apply_cinematic_filter',
    'MovieInfoFetcher',
    'auto_detect_keep_original',
    'auto_generate_cover',
]

