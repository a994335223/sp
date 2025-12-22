# utils/gpu_manager.py - 自动显存管理 + 智能模型选择
"""
SmartVideoClipper - GPU显存管理模块

功能:
1. 自动检测显存大小
2. 根据显存选择最优模型配置
3. 每步后自动清理显存

支持: GTX 1080及以上所有NVIDIA显卡
"""

import torch
import gc


class GPUManager:
    """自动管理GPU显存，支持GTX 1080及以上所有显卡"""
    
    # 不同显存对应的模型配置
    MODEL_CONFIGS = {
        6: {  # 6GB显存 (GTX 1060, RTX 2060)
            'whisper': 'small',
            'clip': 'ViT-B-16',
            'qwen': 'qwen2.5:3b'
        },
        8: {  # 8GB显存 (GTX 1080, RTX 3060) [STAR]推荐
            'whisper': 'medium',
            'clip': 'ViT-B-16',
            'qwen': 'qwen2.5:7b'
        },
        12: {  # 12GB显存 (RTX 3060Ti, RTX 4070)
            'whisper': 'large-v2',
            'clip': 'ViT-L-14',
            'qwen': 'qwen2.5:14b'
        },
        16: {  # 16GB+显存 (RTX 4080, RTX 4090)
            'whisper': 'large-v3',
            'clip': 'ViT-H-14',
            'qwen': 'qwen2.5:32b'
        }
    }
    
    @staticmethod
    def clear():
        """清理GPU显存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
    
    @staticmethod
    def get_total_memory():
        """获取总显存(GB)"""
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / 1024 / 1024 / 1024
        return 0
    
    @staticmethod
    def get_free_memory():
        """获取剩余显存(MB)"""
        if torch.cuda.is_available():
            free = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
            return free / 1024 / 1024
        return 0
    
    @classmethod
    def get_optimal_config(cls):
        """
        🔥 自动检测显存大小，返回最优模型配置
        支持GTX 1080及以上所有NVIDIA显卡
        """
        total_gb = cls.get_total_memory()
        
        # 选择合适的配置档位
        if total_gb >= 16:
            config_key = 16
        elif total_gb >= 12:
            config_key = 12
        elif total_gb >= 8:
            config_key = 8
        else:
            config_key = 6
        
        config = cls.MODEL_CONFIGS[config_key]
        print(f"[GPU] 检测到显存: {total_gb:.1f}GB")
        print(f"[LIST] 自动选择配置: Whisper={config['whisper']}, CLIP={config['clip']}, Qwen={config['qwen']}")
        
        return config
    
    @staticmethod
    def is_cuda_available():
        """检查CUDA是否可用"""
        return torch.cuda.is_available()
    
    @staticmethod
    def get_device():
        """获取设备（cuda或cpu）"""
        return "cuda" if torch.cuda.is_available() else "cpu"
    
    @staticmethod
    def get_device_name():
        """获取GPU名称"""
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        return "CPU"


# 模块级别变量，方便其他模块使用
config = None


def init_config():
    """初始化配置（启动时调用一次）"""
    global config
    config = GPUManager.get_optimal_config()
    return config


# 使用示例
if __name__ == "__main__":
    print("=" * 50)
    print("GPU Manager - 显存检测")
    print("=" * 50)
    
    # 检测GPU
    print(f"\nCUDA可用: {GPUManager.is_cuda_available()}")
    print(f"设备: {GPUManager.get_device()}")
    print(f"GPU名称: {GPUManager.get_device_name()}")
    print(f"总显存: {GPUManager.get_total_memory():.1f}GB")
    print(f"剩余显存: {GPUManager.get_free_memory():.0f}MB")
    
    # 获取最优配置
    print("\n获取最优配置:")
    config = GPUManager.get_optimal_config()
    
    print("\n测试显存清理:")
    GPUManager.clear()
    print("[OK] 显存已清理")
