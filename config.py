from pydantic import BaseModel
from typing import Optional


class NeoTelMeConfig(BaseModel):
    """Neo-tel-me 插件配置"""
    
    class Plugin(BaseModel):
        """插件基础配置"""
        enable_cooldown: bool = False
        cooldown_minutes: float = 5.0
        inject_system_prompt: bool = True  # 是否注入系统提示词
    
    class AliyunASR(BaseModel):
        """阿里云ASR配置"""
        access_key_id: str = ""
        access_key_secret: str = ""
        appkey: str = ""
        sample_rate: int = 16000
        format: str = "pcm"
    
    class MiniMaxTTS(BaseModel):
        """MiniMax TTS配置"""
        api_key: str = ""
        voice_id: str = ""
        model: str = "speech-2.8-hd"
        sample_rate: int = 24000
        speed: float = 1.0
        volume: float = 1.0
        pitch: float = 0.0
    
    class Audio(BaseModel):
        """音频配置"""
        sample_rate: int = 16000
        chunk: int = 1024
        vad_threshold: int = 800
    
    plugin: Plugin = Plugin()
    aliyun_asr: AliyunASR = AliyunASR()
    minimax_tts: MiniMaxTTS = MiniMaxTTS()
    audio: Audio = Audio()