# core/tts_synthesis.py - 语音合成
"""
SmartVideoClipper - 语音合成模块

功能: 将解说文案转换为语音
支持: ChatTTS (高质量) 和 Edge-TTS (稳定)

依赖: edge-tts, ChatTTS(可选)
"""

import torch
import edge_tts
import asyncio
import os

# ChatTTS可选导入（如果安装失败，使用Edge-TTS替代）
CHATTTS_AVAILABLE = False
try:
    import ChatTTS
    import torchaudio
    CHATTTS_AVAILABLE = True
except ImportError:
    print("⚠️ ChatTTS未安装，将使用Edge-TTS作为替代（效果也很好！）")


class TTSEngine:
    """语音合成引擎（支持ChatTTS和Edge-TTS）
    
    💡 推荐：
    - ChatTTS: 效果更自然，但需要GPU和较复杂的安装
    - Edge-TTS: 微软云端TTS，免费、稳定、无需GPU
    """
    
    def __init__(self, engine: str = "auto"):
        """
        初始化TTS引擎
        
        参数:
            engine: 
                "auto" - 自动选择（优先ChatTTS，失败则用Edge-TTS）
                "chattts" - 强制使用ChatTTS
                "edge" - 使用Edge-TTS（推荐，更稳定）
        """
        # 自动选择引擎
        if engine == "auto":
            self.engine = "chattts" if CHATTTS_AVAILABLE else "edge"
        else:
            self.engine = engine
        
        self.chat = None
        self.speaker = None
        
        if self.engine == "chattts":
            if not CHATTTS_AVAILABLE:
                print("⚠️ ChatTTS不可用，切换到Edge-TTS")
                self.engine = "edge"
            else:
                self._init_chattts()
        
        print(f"🔊 TTS引擎: {self.engine.upper()}")
    
    def _init_chattts(self):
        """初始化ChatTTS"""
        try:
            print("🔊 加载ChatTTS模型...")
            self.chat = ChatTTS.Chat()
            self.chat.load(compile=False)  # 大多数显卡不需要compile
            # 生成一个固定音色（可保存复用）
            self.speaker = self.chat.sample_random_speaker()
            print("✅ ChatTTS加载完成")
        except Exception as e:
            print(f"⚠️ ChatTTS加载失败: {e}")
            print("   切换到Edge-TTS")
            self.engine = "edge"
    
    def synthesize_chattts(self, text: str, output_path: str):
        """使用ChatTTS合成"""
        if not self.chat:
            raise RuntimeError("ChatTTS未初始化")
        
        # ChatTTS API（兼容多个版本）
        try:
            # 新版API
            params_infer = ChatTTS.Chat.InferCodeParams(
                spk_emb=self.speaker,
                temperature=0.3,
                top_P=0.7,
                top_K=20,
            )
            params_refine = ChatTTS.Chat.RefineTextParams(
                prompt='[oral_2][laugh_0][break_5]'
            )
            wavs = self.chat.infer(
                text,
                params_infer_code=params_infer,
                params_refine_text=params_refine,
            )
        except AttributeError:
            # 旧版API兼容
            wavs = self.chat.infer(
                text,
                use_decoder=True,
                skip_refine_text=False,
            )
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存音频
        import torchaudio
        torchaudio.save(output_path, torch.from_numpy(wavs[0]), 24000)
        print(f"✅ ChatTTS合成完成: {output_path}")
    
    async def synthesize_edge(self, text: str, output_path: str, voice: str = "zh-CN-YunxiNeural"):
        """
        使用Edge-TTS合成（更稳定）
        
        参数:
            text: 要合成的文本
            output_path: 输出音频路径
            voice: 语音角色
                - zh-CN-YunxiNeural: 男声（推荐）
                - zh-CN-XiaoxiaoNeural: 女声
                - zh-CN-YunjianNeural: 男声（浑厚）
        """
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"✅ Edge-TTS合成完成: {output_path}")
    
    async def synthesize(self, text: str, output_path: str):
        """
        统一接口（异步）
        
        参数:
            text: 要合成的文本
            output_path: 输出音频路径
        """
        if self.engine == "chattts":
            self.synthesize_chattts(text, output_path)
        else:
            await self.synthesize_edge(text, output_path)
    
    def __del__(self):
        """清理资源"""
        if self.chat:
            del self.chat
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# 使用示例
if __name__ == "__main__":
    # 测试TTS
    tts = TTSEngine("edge")  # 使用Edge-TTS（更稳定）
    
    script = """
    话说这部电影一开场，男主就展示了什么叫做社恐天花板。
    你看他进电梯，全程低头玩手机，生怕和邻居对视。
    诶，这不就是每天的我吗？
    """
    
    print("开始语音合成测试...")
    asyncio.run(tts.synthesize(script, "test_narration.wav"))
    print("测试完成！")

