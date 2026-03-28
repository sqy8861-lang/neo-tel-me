import asyncio
from typing import Optional

from src.core.components.base.service import BaseService
from src.kernel.logger import get_logger

from .aliyun_asr import AliyunRealtimeASR
from .minimax_tts import MiniMaxTTS
from .audio_manager import AudioManager
from .llm_config import LLMConfig
from .llm_client import LLMClient
from .prompt_refiner import PromptRefiner
from .memory_manager import MemoryManager
from .history_manager import HistoryManager

logger = get_logger("neo_tel_me")


class NeoTelMeService(BaseService):
    """Neo-tel-me 服务"""
    
    service_name: str = "neo_tel_me"
    service_description: str = "实时语音对话服务，支持阿里云ASR和MiniMax TTS"
    version: str = "1.1.0"
    update_info: str = "更新：集成阿里云智能语音交互Python SDK，实现Token自动获取和实时语音识别功能"
    """
    Neo-tel-me 服务
    """
    
    def __init__(self, plugin):
        """
        初始化服务
        
        Args:
            plugin: 插件实例
        """
        super().__init__(plugin)
        self.asr = None
        self.tts = None
        self.audio_manager = None
        self.is_running = False
        self.current_tts_task = None
        
        # LLM相关组件
        self.llm_config = None
        self.llm_client = None
        self.prompt_refiner = None
        self.memory_manager = None
        self.history_manager = None
        self.llm_initialized = False
    
    def _cfg(self):
        """
        获取插件配置
        
        Returns:
            NeoTelMeConfig: 插件配置
        """
        from .config import NeoTelMeConfig
        cfg = self.plugin.config
        if not isinstance(cfg, NeoTelMeConfig):
            raise RuntimeError("neo_tel_me plugin config 未正确加载")
        return cfg
    
    async def start(self):
        """
        启动服务
        """
        try:
            # 初始化LLM组件
            await self._initialize_llm()
            
            # 初始化音频管理器
            self.audio_manager = AudioManager(
                sample_rate=self._cfg().audio.sample_rate,
                chunk=self._cfg().audio.chunk,
                vad_threshold=self._cfg().audio.vad_threshold
            )
            
            # 初始化阿里云ASR
            self.asr = AliyunRealtimeASR(
                appkey=self._cfg().aliyun_asr.appkey,
                access_key_id=self._cfg().aliyun_asr.access_key_id,
                access_key_secret=self._cfg().aliyun_asr.access_key_secret,
                sample_rate=self._cfg().aliyun_asr.sample_rate,
                format=self._cfg().aliyun_asr.format
            )
            
            # 初始化MiniMax TTS
            self.tts = MiniMaxTTS(
                api_key=self._cfg().minimax_tts.api_key,
                voice_id=self._cfg().minimax_tts.voice_id,
                model=self._cfg().minimax_tts.model
            )
            
            # 连接ASR
            connected = await self.asr.connect(self._on_asr_result)
            if not connected:
                print("❌ ASR 连接失败，服务启动失败")
                return False
            
            # 开始音频采集
            self.audio_manager.start_recording(
                audio_callback=self._on_audio_data,
                vad_callback=self._on_vad
            )
            
            self.is_running = True
            logger.info("Neo-tel-me 服务已启动！")
            logger.info("提示：说话即可，AI 会自动回复；大声说话可打断 AI")
            return True
        except Exception as e:
            logger.error(f"服务启动失败: {e}")
            return False
    
    async def _initialize_llm(self):
        """
        初始化LLM组件
        """
        try:
            # 加载LLM配置（从插件自身的配置）
            cfg = self._cfg()
            self.llm_config = LLMConfig()
            self.llm_config.model.provider = cfg.llm.model.provider
            self.llm_config.model.model_name = cfg.llm.model.model_name
            self.llm_config.model.api_key = cfg.llm.model.api_key
            self.llm_config.model.base_url = cfg.llm.model.base_url
            self.llm_config.model.temperature = cfg.llm.model.temperature
            self.llm_config.model.max_tokens = cfg.llm.model.max_tokens
            
            # 初始化LLM客户端
            self.llm_client = LLMClient(self.llm_config)
            await self.llm_client.initialize()
            
            # 初始化提示词精炼器
            self.prompt_refiner = PromptRefiner()
            personality_prompt = await self.prompt_refiner.initialize(self.llm_client)
            self.llm_client.set_system_prompt(personality_prompt)
            
            # 初始化记忆管理器
            self.memory_manager = MemoryManager()
            # 这里可以传入booku_memory服务实例
            # self.memory_manager.initialize(booku_memory_service)
            memory_prompt = await self.memory_manager.generate_memory_prompt(self.llm_client)
            self.llm_client.set_memory_prompt(memory_prompt)
            
            # 初始化历史记录管理器
            self.history_manager = HistoryManager(max_history=cfg.llm.prompt.max_history)
            
            self.llm_initialized = True
            logger.info("LLM组件初始化完成")
        except Exception as e:
            logger.error(f"LLM组件初始化失败: {e}")
            self.llm_initialized = False
    
    async def stop(self):
        """
        停止服务
        """
        try:
            self.is_running = False
            
            # 停止音频采集
            if self.audio_manager:
                self.audio_manager.close()
            
            # 关闭ASR连接
            if self.asr:
                await self.asr.close()
            
            # 取消当前TTS任务
            if self.current_tts_task:
                self.current_tts_task.cancel()
                try:
                    await self.current_tts_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭LLM客户端
            if self.llm_client:
                await self.llm_client.close()
            
            logger.info("Neo-tel-me 服务已停止")
        except Exception as e:
            logger.error(f"服务停止失败: {e}")
    
    async def _on_audio_data(self, audio_data: bytes):
        """
        音频数据回调
        
        Args:
            audio_data: 音频数据
        """
        if self.asr and self.asr.connected:
            await self.asr.send_audio(audio_data)
    
    def _on_vad(self, volume: float):
        """
        语音活动检测回调
        
        Args:
            volume: 音量
        """
        # 如果AI正在说话，且检测到较大音量，触发打断
        if self.tts and self.tts.is_playing() and volume > self._cfg().audio.vad_threshold:
            self.tts.interrupt()
            logger.info("用户打断 AI")
    
    async def _on_asr_result(self, text: str):
        """
        ASR识别结果回调
        
        Args:
            text: 识别文本
        """
        logger.info(f"用户说: {text}")
        
        # 打断当前AI说话
        if self.tts and self.tts.is_playing():
            self.tts.interrupt()
            if self.current_tts_task:
                self.current_tts_task.cancel()
                try:
                    await self.current_tts_task
                except asyncio.CancelledError:
                    pass
        
        # 添加用户消息到历史记录
        if self.history_manager:
            self.history_manager.add_user_message(text)
        
        # 使用LLM生成回复
        reply = await self._generate_reply(text)
        logger.info(f"AI 说: {reply}")
        
        # 添加AI回复到历史记录
        if self.history_manager:
            self.history_manager.add_assistant_message(reply)
        
        # 播放TTS
        self.current_tts_task = asyncio.create_task(self._play_tts(reply))
    
    async def _generate_reply(self, user_input: str) -> str:
        """
        生成AI回复
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            str: AI回复
        """
        if not self.llm_initialized or not self.llm_client:
            # LLM未初始化，使用模拟回复
            return self._get_mock_reply(user_input)
        
        try:
            # 获取历史记录
            history_text = self.history_manager.format_for_llm() if self.history_manager else "暂无对话历史"
            
            # 使用LLM生成回复
            reply = await self.llm_client.generate_response(user_input, history_text)
            
            if reply:
                return reply
            else:
                logger.warning("LLM返回空回复，使用模拟回复")
                return self._get_mock_reply(user_input)
        except Exception as e:
            logger.error(f"LLM生成回复失败: {e}")
            return self._get_mock_reply(user_input)
    
    def _get_mock_reply(self, text: str) -> str:
        """
        获取模拟回复（暂时搁置LLM）
        
        Args:
            text: 用户输入文本
            
        Returns:
            str: 模拟回复
        """
        # 简单的模拟回复
        mock_replies = {
            "你好": "你好！很高兴见到你。",
            "你是谁": "我是Neo-tel-me，一个实时语音对话助手。",
            "天气怎么样": "今天天气很好，适合外出活动。",
            "再见": "再见！期待下次和你聊天。"
        }
        
        # 寻找关键词
        for key, reply in mock_replies.items():
            if key in text:
                return reply
        
        # 默认回复
        return f"我听到你说: {text}，这是一个模拟回复。"
    
    async def _play_tts(self, text: str):
        """
        播放TTS
        
        Args:
            text: 要合成的文本
        """
        if not self.tts:
            return
        
        try:
            async for audio_data in self.tts.tts_stream(
                text=text,
                speed=self._cfg().minimax_tts.speed,
                volume=self._cfg().minimax_tts.volume,
                pitch=self._cfg().minimax_tts.pitch,
                sample_rate=self._cfg().minimax_tts.sample_rate
            ):
                if self.audio_manager:
                    self.audio_manager.play_audio(
                        audio_data,
                        sample_rate=self._cfg().minimax_tts.sample_rate
                    )
        except Exception as e:
            logger.error(f"TTS 播放错误: {e}")
    
    def is_service_running(self) -> bool:
        """
        检查服务是否运行
        
        Returns:
            bool: 服务是否运行
        """
        return self.is_running