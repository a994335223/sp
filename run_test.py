# -*- coding: utf-8 -*-
"""临时测试脚本"""
import asyncio
import sys
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "0"

sys.path.insert(0, '.')
sys.path.insert(0, './core')

from app.main_auto import full_auto_process

if __name__ == "__main__":
    asyncio.run(full_auto_process(
        input_video=r'C:\Users\Administrator\Downloads\狂飙E01.mp4',
        movie_name='狂飙',
        output_name='狂飙第一集解说',
        style='幽默吐槽',
        use_internet=True,
        target_duration=600
    ))

