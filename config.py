from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class NeoTelMeConfig(BaseConfig):
    """Neo-tel-me 插件配置"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "Neo-tel-me 实时语音对话插件配置"
    
    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基础配置"""
        enable_cooldown: bool = Field(default=False, description="是否启用冷却时间")
        cooldown_minutes: float = Field(default=5.0, description="冷却时间（分钟）")
    
    @config_section("aliyun_asr")
    class AliyunASRSection(SectionBase):
        """阿里云ASR配置"""
        access_key_id: str = Field(default="", description="阿里云Access Key ID")
        access_key_secret: str = Field(default="", description="阿里云Access Key Secret")
        appkey: str = Field(default="", description="阿里云ASR AppKey")
        sample_rate: int = Field(default=16000, description="采样率")
        format: str = Field(default="pcm", description="音频格式")
    
    @config_section("minimax_tts")
    class MiniMaxTTSSection(SectionBase):
        """MiniMax TTS配置"""
        api_key: str = Field(default="", description="MiniMax API Key")
        voice_id: str = Field(default="", description="语音ID")
        model: str = Field(default="speech-2.8-hd", description="TTS模型")
        sample_rate: int = Field(default=24000, description="采样率")
        speed: float = Field(default=1.0, description="语速")
        volume: float = Field(default=1.0, description="音量")
        pitch: float = Field(default=0.0, description="音调")
    
    @config_section("audio")
    class AudioSection(SectionBase):
        """音频配置"""
        sample_rate: int = Field(default=16000, description="采样率")
        chunk: int = Field(default=1024, description="音频块大小")
        vad_threshold: int = Field(default=800, description="语音活动检测阈值")
    
    plugin: PluginSection = Field(default_factory=PluginSection)
    aliyun_asr: AliyunASRSection = Field(default_factory=AliyunASRSection)
    minimax_tts: MiniMaxTTSSection = Field(default_factory=MiniMaxTTSSection)
    audio: AudioSection = Field(default_factory=AudioSection)