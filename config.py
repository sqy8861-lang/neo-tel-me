from __future__ import annotations

from typing import ClassVar

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


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
        access_key_secret: str = Field(
            default="", description="阿里云Access Key Secret"
        )
        appkey: str = Field(default="", description="阿里云ASR AppKey")
        sample_rate: int = Field(default=16000, description="采样率")
        format: str = Field(default="pcm", description="音频格式")

    @config_section("minimax_tts")
    class MiniMaxTTSSection(SectionBase):
        """MiniMax TTS配置"""

        api_key: str = Field(default="", description="MiniMax API Key")
        voice_id: str = Field(default="", description="语音ID")
        model: str = Field(default="speech-2.6-turbo", description="TTS模型")
        sample_rate: int = Field(default=16000, description="采样率")
        format: str = Field(default="pcm", description="音频格式")
        speed: float = Field(default=1.0, description="语速")
        volume: float = Field(default=1.0, description="音量")
        pitch: int = Field(default=0, description="音调")

    @config_section("audio")
    class AudioSection(SectionBase):
        """音频配置"""

        sample_rate: int = Field(default=16000, description="采样率")
        chunk: int = Field(default=512, description="音频块大小（优化延迟）")
        vad_threshold: int = Field(
            default=600, description="语音活动检测阈值（优化响应速度）"
        )

    @config_section("websocket")
    class WebSocketSection(SectionBase):
        """WebSocket配置"""

        enabled: bool = Field(
            default=False, description="是否启用WebSocket模式（用于H5前端）"
        )
        host: str = Field(default="0.0.0.0", description="WebSocket服务器主机地址")
        port: int = Field(default=8766, description="WebSocket服务器端口")
        public_ip: str = Field(
            default="", description="服务器公网IP（可选，留空则使用host）"
        )
        audio_format: str = Field(default="pcm", description="音频格式（pcm或mp3）")
        use_ssl: bool = Field(default=False, description="是否启用SSL/TLS（HTTPS/WSS）")
        ssl_cert: str = Field(default="", description="SSL证书文件路径（.pem或.crt）")
        ssl_key: str = Field(default="", description="SSL私钥文件路径（.key）")

    @config_section("llm")
    class LLMSection(SectionBase):
        """LLM配置"""

        @config_section("model")
        class ModelSection(SectionBase):
            """模型配置"""

            provider: str = Field(default="openai", description="模型提供商")
            model_name: str = Field(default="gpt-4", description="模型名称")
            api_key: str = Field(default="", description="API密钥")
            base_url: str = Field(default=None, description="API基础URL")
            temperature: float = Field(default=0.7, description="温度参数")
            max_tokens: int = Field(default=1000, description="最大token数")

        @config_section("prompt")
        class PromptSection(SectionBase):
            """提示词配置"""

            personality_prompt: str = Field(default="", description="性格提示词")
            memory_prompt: str = Field(default="", description="记忆提示词")
            max_history: int = Field(default=4, description="最近历史记录数量")

        @config_section("memory")
        class MemorySection(SectionBase):
            """记忆配置"""

            recent_count: int = Field(default=5, description="近期记忆数量")
            important_only: bool = Field(default=True, description="只获取重要记忆")

        model: ModelSection = Field(default_factory=ModelSection)
        prompt: PromptSection = Field(default_factory=PromptSection)
        memory: MemorySection = Field(default_factory=MemorySection)

    plugin: PluginSection = Field(default_factory=PluginSection)
    aliyun_asr: AliyunASRSection = Field(default_factory=AliyunASRSection)
    minimax_tts: MiniMaxTTSSection = Field(default_factory=MiniMaxTTSSection)
    audio: AudioSection = Field(default_factory=AudioSection)
    websocket: WebSocketSection = Field(default_factory=WebSocketSection)
    llm: LLMSection = Field(default_factory=LLMSection)
