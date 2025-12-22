# core/gpu_encoder.py - GPU硬件加速编码器
"""
SmartVideoClipper - GPU硬件加速支持

支持的硬件加速：
- NVIDIA NVENC (推荐，速度最快)
- Intel QSV (Intel核显)
- AMD AMF (AMD显卡)
- 软件编码 (fallback)

性能对比（1080p视频）：
- libx264 (CPU): ~30fps
- h264_nvenc (NVIDIA): ~300fps (10倍提升!)
- h264_qsv (Intel): ~150fps
"""

import subprocess
import os
from typing import Tuple, List, Optional
from functools import lru_cache


class GPUEncoder:
    """
    GPU硬件加速编码器
    
    自动检测可用的硬件编码器，优先使用最快的
    """
    
    # 编码器优先级（从快到慢）
    ENCODER_PRIORITY = [
        ('h264_nvenc', 'NVIDIA NVENC'),      # NVIDIA显卡
        ('h264_qsv', 'Intel QuickSync'),     # Intel核显
        ('h264_amf', 'AMD AMF'),             # AMD显卡
        ('libx264', 'CPU软件编码'),           # 软件编码（fallback）
    ]
    
    def __init__(self):
        self.available_encoder = None
        self.encoder_name = None
        self._detect_encoder()
    
    def _detect_encoder(self):
        """检测可用的硬件编码器"""
        print("[GPU] 检测硬件加速支持...")
        
        for encoder, name in self.ENCODER_PRIORITY:
            if self._test_encoder(encoder):
                self.available_encoder = encoder
                self.encoder_name = name
                print(f"   [OK] 使用 {name} ({encoder})")
                return
        
        # fallback
        self.available_encoder = 'libx264'
        self.encoder_name = 'CPU软件编码'
        print(f"   [WARN] 无硬件加速，使用CPU编码")
    
    def _test_encoder(self, encoder: str) -> bool:
        """测试编码器是否可用"""
        try:
            # 使用ffmpeg测试编码器
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', 'testsrc=duration=0.1:size=64x64:rate=1',
                '-c:v', encoder,
                '-f', 'null', '-'
            ]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                encoding='utf-8', 
                errors='ignore',
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_video_codec_args(self, quality: str = 'fast') -> List[str]:
        """
        获取视频编码参数
        
        参数：
            quality: 'fast' (速度优先) 或 'quality' (质量优先)
        
        返回：
            FFmpeg参数列表
        """
        encoder = self.available_encoder
        
        if encoder == 'h264_nvenc':
            # NVIDIA NVENC
            if quality == 'fast':
                return ['-c:v', 'h264_nvenc', '-preset', 'p4', '-tune', 'hq']
            else:
                return ['-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq', '-rc', 'vbr', '-cq', '19']
        
        elif encoder == 'h264_qsv':
            # Intel QuickSync
            if quality == 'fast':
                return ['-c:v', 'h264_qsv', '-preset', 'fast']
            else:
                return ['-c:v', 'h264_qsv', '-preset', 'slow', '-global_quality', '20']
        
        elif encoder == 'h264_amf':
            # AMD AMF
            if quality == 'fast':
                return ['-c:v', 'h264_amf', '-quality', 'speed']
            else:
                return ['-c:v', 'h264_amf', '-quality', 'quality']
        
        else:
            # libx264 软件编码
            if quality == 'fast':
                return ['-c:v', 'libx264', '-preset', 'fast']
            else:
                return ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18']
    
    def get_info(self) -> dict:
        """获取编码器信息"""
        return {
            'encoder': self.available_encoder,
            'name': self.encoder_name,
            'is_hardware': self.available_encoder != 'libx264',
        }


# 全局单例
_encoder_instance = None


def get_encoder() -> GPUEncoder:
    """获取全局编码器实例"""
    global _encoder_instance
    if _encoder_instance is None:
        _encoder_instance = GPUEncoder()
    return _encoder_instance


def get_video_codec_args(quality: str = 'fast') -> List[str]:
    """快捷函数：获取视频编码参数"""
    return get_encoder().get_video_codec_args(quality)


def is_hardware_available() -> bool:
    """快捷函数：检查是否有硬件加速"""
    return get_encoder().available_encoder != 'libx264'


# 测试
if __name__ == "__main__":
    encoder = GPUEncoder()
    print(f"\n编码器信息: {encoder.get_info()}")
    print(f"快速模式参数: {encoder.get_video_codec_args('fast')}")
    print(f"质量模式参数: {encoder.get_video_codec_args('quality')}")

