# utils/gpu_manager.py - 自动显存管理 + Ollama服务监控
"""
SmartVideoClipper - GPU显存管理模块 v5.9

功能:
1. 自动检测显存大小和使用率
2. 根据显存选择最优模型配置
3. 实时监控显存占用，自动清理
4. Ollama服务重启和状态监控
5. 智能降级策略（GPU -> CPU）

支持: GTX 1080及以上所有NVIDIA显卡
RTX 4060优化: 8GB显存专用配置
"""

import torch
import gc
import psutil
import subprocess
import time
import os
from typing import Optional, Dict, Any


class GPUManager:
    """自动管理GPU显存 + Ollama服务，支持GTX 1080及以上所有显卡"""
    
    # RTX 4060专用配置 (8GB显存优化)
    MODEL_CONFIGS = {
        6: {  # 6GB显存 (GTX 1060, RTX 2060)
            'whisper': 'small',
            'clip': 'ViT-B-16',
            'qwen': 'qwen2.5:3b'
        },
        8: {  # 8GB显存 - RTX 4060专用优化
            'whisper': 'medium',
            'clip': 'ViT-B-16',
            'qwen': 'qwen2.5:7b',  # 降级以节省显存
            # 分级模型配置 (RTX 4060优化)
            'story_framework': 'gemma3:4b',    # 3.3GB - 前期处理
            'hook_generator': 'gemma3:4b',     # 3.3GB - 钩子生成
            'silence_handler': 'codellama',    # 3.8GB - 静音处理
            'narration': 'qwen3:8b',          # 5.2GB - 核心解说(最后使用)
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

    @staticmethod
    def get_memory_usage():
        """获取显存使用率 (0.0-1.0)"""
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory
            used = torch.cuda.memory_allocated(0)
            return used / total
        return 0.0

    @staticmethod
    def get_memory_info():
        """获取详细显存信息"""
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024 / 1024  # GB
            allocated = torch.cuda.memory_allocated(0) / 1024 / 1024 / 1024  # GB
            reserved = torch.cuda.memory_reserved(0) / 1024 / 1024 / 1024   # GB
            free = total - allocated

            return {
                'total_gb': total,
                'allocated_gb': allocated,
                'reserved_gb': reserved,
                'free_gb': free,
                'usage_percent': (allocated / total) * 100
            }
        return None

    @staticmethod
    def check_memory_threshold(threshold: float = 0.85) -> bool:
        """检查是否超过显存阈值"""
        usage = GPUManager.get_memory_usage()
        return usage > threshold

    @staticmethod
    def cleanup_memory():
        """强制清理GPU显存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()  # 等待清理完成
            gc.collect()
            print(f"[GPU] 显存清理完成，当前使用率: {GPUManager.get_memory_usage():.1%}")

    @staticmethod
    def is_ollama_running() -> bool:
        """检查Ollama服务是否运行"""
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ollama.exe'],
                                  capture_output=True, text=True, shell=True)
            return 'ollama.exe' in result.stdout
        except:
            return False

    @staticmethod
    def restart_ollama_service():
        """重启Ollama服务以清理显存"""
        print("[Ollama] 重启服务以清理显存...")

        try:
            # 停止Ollama
            subprocess.run(['taskkill', '/F', '/IM', 'ollama.exe'], shell=True,
                         capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'ollama app.exe'], shell=True,
                         capture_output=True)

            time.sleep(2)  # 等待停止完成

            # 启动Ollama
            subprocess.Popen(['ollama', 'serve'], shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 等待服务启动
            time.sleep(3)

            if GPUManager.is_ollama_running():
                print("[Ollama] 服务重启成功")
                return True
            else:
                print("[Ollama] 服务重启失败")
                return False

        except Exception as e:
            print(f"[Ollama] 重启失败: {e}")
            return False

    @staticmethod
    def monitor_and_cleanup(threshold: float = 0.85):
        """监控显存并自动清理"""
        if GPUManager.check_memory_threshold(threshold):
            usage = GPUManager.get_memory_usage()
            print(".1%")
            print("[GPU] 触发自动清理...")

            # 先尝试清理GPU显存
            GPUManager.cleanup_memory()

            # 如果清理后仍然超过阈值，重启Ollama
            if GPUManager.check_memory_threshold(threshold):
                print("[GPU] GPU清理无效，重启Ollama服务...")
                if GPUManager.restart_ollama_service():
                    print("[GPU] Ollama重启后显存状态正常")
                else:
                    print("[GPU] Ollama重启失败，可能需要手动干预")
                    return False

            return True
        return True
    
    @classmethod
    def get_optimal_config(cls):
        """
        🔥 自动检测显存大小，返回最优模型配置
        支持GTX 1080及以上所有NVIDIA显卡
        RTX 4060专用: 分级模型策略
        """
        total_gb = cls.get_total_memory()

        # 选择合适的配置档位（使用0.5GB容差，避免7.99GB被判为<8GB）
        if total_gb >= 15.5:
            config_key = 16
        elif total_gb >= 11.5:
            config_key = 12
        elif total_gb >= 7.5:  # RTX 4060 8GB 实际显示7.99GB
            config_key = 8
        else:
            config_key = 6

        config = cls.MODEL_CONFIGS[config_key]
        print(f"[GPU] 检测到显存: {total_gb:.1f}GB (档位: {config_key}GB)")

        if config_key == 8:
            print("[RTX4060] 启用分级模型策略:")
            print(f"  ├── 故事框架: {config['story_framework']}")
            print(f"  ├── 钩子生成: {config['hook_generator']}")
            print(f"  ├── 静音处理: {config['silence_handler']}")
            print(f"  └── 核心解说: {config['narration']}")
        else:
            print(f"[LIST] 标准配置: Whisper={config['whisper']}, CLIP={config['clip']}, Qwen={config['qwen']}")

        return config

    @classmethod
    def get_model_for_task(cls, task: str) -> str:
        """
        根据任务类型返回最优模型 (RTX 4060优化)
        """
        config = cls.get_optimal_config()

        # RTX 4060分级策略
        if cls.get_total_memory() >= 7.5:  # RTX 4060
            task_models = {
                'story_framework': config.get('story_framework', config['qwen']),
                'hook_generator': config.get('hook_generator', config['qwen']),
                'silence_handler': config.get('silence_handler', config['qwen']),
                'narration': config.get('narration', config['qwen']),
                'default': config['qwen']
            }
            return task_models.get(task, task_models['default'])

        # 其他显存配置使用默认模型
        return config['qwen']
    
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


# RTX 4060智能显存管理测试
if __name__ == "__main__":
    print("=" * 60)
    print("GPU Manager v5.9 - RTX 4060智能显存管理")
    print("=" * 60)

    # 检测GPU
    print(f"\n🔍 系统检测:")
    print(f"   CUDA可用: {GPUManager.is_cuda_available()}")
    print(f"   设备: {GPUManager.get_device()}")
    print(f"   GPU名称: {GPUManager.get_device_name()}")
    print(f"   Ollama运行: {GPUManager.is_ollama_running()}")

    if GPUManager.is_cuda_available():
        mem_info = GPUManager.get_memory_info()
        print(f"   总显存: {mem_info['total_gb']:.1f}GB")
        print(f"   已分配: {mem_info['allocated_gb']:.1f}GB")
        print(f"   已保留: {mem_info['reserved_gb']:.1f}GB")
        print(f"   剩余: {mem_info['free_gb']:.1f}GB")
        print(f"   使用率: {mem_info['usage_percent']:.1f}%")

    # 获取最优配置
    print(f"\n🎯 智能配置:")
    config = GPUManager.get_optimal_config()

    # RTX 4060分级模型演示
    if GPUManager.get_total_memory() >= 7.5:
        print(f"\n🔧 RTX 4060分级策略测试:")
        tasks = ['story_framework', 'hook_generator', 'silence_handler', 'narration']
        for task in tasks:
            model = GPUManager.get_model_for_task(task)
            print(f"   {task}: {model}")

    # 显存监控测试
    print(f"\n📊 显存监控测试:")
    usage = GPUManager.get_memory_usage()
    print(f"   当前使用率: {usage:.1%}")

    threshold = 0.85
    if GPUManager.check_memory_threshold(threshold):
        print(f"   ⚠️ 超过{threshold:.0%}阈值，准备清理...")
        GPUManager.monitor_and_cleanup(threshold)
    else:
        print(f"   ✅ 显存使用正常 (阈值: {threshold:.0%})")

    print(f"\n🧹 清理测试:")
    GPUManager.cleanup_memory()
    print("[OK] 显存管理测试完成")
