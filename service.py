import asyncio
from typing import Optional
import json
from pathlib import Path

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
from .websocket_handler import WebSocketHandler

logger = get_logger("neo_tel_me")

# 提示词存储路径
import os
# 计算主项目根目录（向上两级）
PROJECT_ROOT = Path(__file__).parent.parent.parent
# 在data目录下创建专门的插件文件夹
DATA_DIR = PROJECT_ROOT / "data" / "neo_tel_me"
MEMORY_PROMPT_FILE = DATA_DIR / "memory_prompt.json"


class NeoTelMeService(BaseService):
    """Neo-tel-me 服务"""
    
    service_name: str = "neo_tel_me"
    service_description: str = "实时语音对话服务，支持阿里云ASR和MiniMax TTS"
    version: str = "1.1.0"
    update_info: str = "更新：集成阿里云智能语音交互Python SDK，实现Token自动获取和实时语音识别功能"
    """
    Neo-tel-me 服务
    """
    
    def __init__(self, plugin, system_prompt: str = ""):
        """
        初始化服务
        
        Args:
            plugin: 插件实例
            system_prompt: 系统提示词
        """
        super().__init__(plugin)
        self.asr = None
        self.tts = None
        self.audio_manager = None
        self.is_running = False
        self.current_tts_task = None
        self.user_nickname = ""
        self.system_prompt = system_prompt
        
        self.llm_config = None
        self.llm_client = None
        self.prompt_refiner = None
        self.memory_manager = None
        self.history_manager = None
        self.llm_initialized = False
        
        # WebSocket相关组件
        self.websocket_handler = None
        self.websocket_task = None
    
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
    
    async def start(self, user_nickname: str = ""):
        """
        启动服务
        
        Args:
            user_nickname: 用户昵称，用于连麦时标识用户
        """
        try:
            # 存储用户昵称
            self.user_nickname = user_nickname
            
            # 初始化LLM组件
            await self._initialize_llm()
            
            # 初始化MiniMax TTS
            self.tts = MiniMaxTTS(
                api_key=self._cfg().minimax_tts.api_key,
                voice_id=self._cfg().minimax_tts.voice_id,
                model=self._cfg().minimax_tts.model
            )
            
            # 根据配置选择模式
            if self._cfg().websocket.enabled:
                # WebSocket模式（用于H5前端）
                await self._start_websocket_mode()
            else:
                # 本地模式（使用PyAudio）
                await self._start_local_mode()
            
            self.is_running = True
            logger.info(f"Neo-tel-me 服务已启动！用户昵称: {self.user_nickname}")
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
            
            # 使用传入的系统提示词
            if self.system_prompt:
                logger.info("使用插件加载时生成的系统提示词")
                # 如果有用户昵称，添加到系统提示词中
                if self.user_nickname:
                    personalized_system_prompt = f"{self.system_prompt}\n\n你说话的对象是{self.user_nickname}。"
                    self.llm_client.set_system_prompt(personalized_system_prompt)
                else:
                    self.llm_client.set_system_prompt(self.system_prompt)
            else:
                #  fallback：如果没有系统提示词，生成一个
                logger.warning("没有系统提示词，正在生成默认提示词")
                self.prompt_refiner = PromptRefiner()
                personality_prompt = await self.prompt_refiner.initialize(self.llm_client, user_nickname=self.user_nickname)
                self.llm_client.set_system_prompt(personality_prompt)
            
            # 加载或生成记忆提示词
            memory_prompt = await self._load_or_generate_memory_prompt()
            self.llm_client.set_memory_prompt(memory_prompt)
            
            # 初始化历史记录管理器
            self.history_manager = HistoryManager(max_history=cfg.llm.prompt.max_history)
            
            self.llm_initialized = True
            logger.info("LLM组件初始化完成")
        except Exception as e:
            logger.error(f"LLM组件初始化失败: {e}")
            self.llm_initialized = False
    
    async def _load_or_generate_memory_prompt(self) -> str:
        """
        加载或生成记忆提示词
        
        Returns:
            str: 记忆提示词
        """
        # 尝试加载已存储的记忆提示词
        if MEMORY_PROMPT_FILE.exists():
            try:
                with open(MEMORY_PROMPT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    prompt = data.get('memory_prompt', '')
                    if prompt:
                        logger.info("成功加载已存储的记忆提示词")
                        return prompt
            except Exception as e:
                logger.error(f"加载记忆提示词失败: {e}")
        
        # 生成新的记忆提示词
        logger.info("未找到存储的记忆提示词，正在生成新的")
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager()
        # 这里可以传入booku_memory服务实例
        # self.memory_manager.initialize(booku_memory_service)
        memory_prompt = await self.memory_manager.generate_memory_prompt(self.llm_client, user_nickname=self.user_nickname)
        
        # 存储记忆提示词
        try:
            with open(MEMORY_PROMPT_FILE, 'w', encoding='utf-8') as f:
                json.dump({'memory_prompt': memory_prompt}, f, ensure_ascii=False, indent=2)
            logger.info("记忆提示词已存储")
        except Exception as e:
            logger.error(f"存储记忆提示词失败: {e}")
        
        return memory_prompt
    
    async def _start_local_mode(self):
        """
        启动本地模式（使用PyAudio）
        """
        try:
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
            
            # 连接ASR
            connected = await self.asr.connect(self._on_asr_result)
            if not connected:
                logger.error("❌ ASR 连接失败，服务启动失败")
                raise Exception("ASR 连接失败")
            
            # 开始音频采集
            self.audio_manager.start_recording(
                audio_callback=self._on_audio_data,
                vad_callback=self._on_vad
            )
            
            logger.info("本地模式已启动")
            logger.info("提示：说话即可，AI 会自动回复；大声说话可打断 AI")
            
        except Exception as e:
            logger.error(f"本地模式启动失败: {e}")
            raise
    
    async def _start_websocket_mode(self):
        """
        启动WebSocket模式（用于H5前端）
        """
        try:
            # 初始化WebSocket处理器
            self.websocket_handler = WebSocketHandler(self._cfg())
            
            self.websocket_handler.on_audio_data = self._on_websocket_audio_data
            self.websocket_handler.on_client_connected = self._on_websocket_client_connected
            self.websocket_handler.on_client_disconnected = self._on_websocket_client_disconnected
            self.websocket_handler.on_stop_call = self._on_websocket_stop_call
            
            self.websocket_task = asyncio.create_task(self.websocket_handler.start())
            
            logger.info(f"WebSocket模式已启动，监听 {self._cfg().websocket.host}:{self._cfg().websocket.port}")
            
        except Exception as e:
            logger.error(f"WebSocket模式启动失败: {e}")
            raise
    
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
            
            # 关闭TTS连接
            if self.tts:
                await self.tts.close()
            
            # 关闭LLM客户端
            if self.llm_client:
                await self.llm_client.close()
            
            # 停止WebSocket服务器
            if self.websocket_handler:
                await self.websocket_handler.stop()
            
            if self.websocket_task:
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
            
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
                sample_rate=self._cfg().minimax_tts.sample_rate,
                format=self._cfg().minimax_tts.format
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
    
    async def _on_websocket_audio_data(self, websocket, audio_data: bytes):
        """
        WebSocket音频数据回调
        
        Args:
            websocket: WebSocket连接
            audio_data: 音频数据
        """
        try:
            # 为每个客户端创建独立的ASR连接（如果还没有）
            if not hasattr(websocket, 'asr') or not websocket.asr:
                websocket.asr = AliyunRealtimeASR(
                    appkey=self._cfg().aliyun_asr.appkey,
                    access_key_id=self._cfg().aliyun_asr.access_key_id,
                    access_key_secret=self._cfg().aliyun_asr.access_key_secret,
                    sample_rate=self._cfg().aliyun_asr.sample_rate,
                    format=self._cfg().aliyun_asr.format
                )
                
                # 连接ASR，设置回调函数
                async def on_asr_result(text: str):
                    await self._on_websocket_asr_result(websocket, text)
                
                connected = await websocket.asr.connect(on_asr_result)
                if not connected:
                    logger.error(f"客户端 {websocket.remote_address} ASR 连接失败")
                    return
            
            # 发送音频数据到ASR
            if websocket.asr and websocket.asr.connected:
                await websocket.asr.send_audio(audio_data)
            
        except Exception as e:
            logger.error(f"处理WebSocket音频数据错误: {e}")
    
    async def _on_websocket_asr_result(self, websocket, text: str):
        """
        WebSocket ASR识别结果回调
        
        Args:
            websocket: WebSocket连接
            text: 识别文本
        """
        try:
            if not text or not text.strip():
                return
            
            if not hasattr(websocket, 'remote_address') or websocket.remote_address is None:
                logger.warning(f"客户端已断开，跳过处理")
                return
            
            logger.info(f"客户端 {websocket.remote_address} 用户说: {text}")
            
            if not hasattr(websocket, 'history_manager'):
                websocket.history_manager = HistoryManager(max_history=self._cfg().llm.prompt.max_history)
            
            websocket.history_manager.add_user_message(text)
            
            reply = await self._generate_reply_for_websocket(websocket, text)
            logger.info(f"客户端 {websocket.remote_address} AI 说: {reply}")
            
            websocket.history_manager.add_assistant_message(reply)
            
            await self._generate_and_send_tts_to_websocket(websocket, reply)
            
        except Exception as e:
            logger.error(f"处理WebSocket ASR结果错误: {e}")
    
    async def _generate_reply_for_websocket(self, websocket, text: str) -> str:
        """
        为WebSocket客户端生成AI回复
        
        Args:
            websocket: WebSocket连接
            text: 用户输入文本
            
        Returns:
            str: AI回复
        """
        if not self.llm_initialized or not self.llm_client:
            return self._get_mock_reply(text)
        
        try:
            # 获取历史记录
            history_text = websocket.history_manager.format_for_llm() if hasattr(websocket, 'history_manager') else "暂无对话历史"
            
            # 使用LLM生成回复
            reply = await self.llm_client.generate_response(text, history_text)
            
            if reply:
                return reply
            else:
                logger.warning("LLM返回空回复，使用模拟回复")
                return self._get_mock_reply(text)
        except Exception as e:
            logger.error(f"LLM生成回复失败: {e}")
            return self._get_mock_reply(text)
    
    async def _generate_and_send_tts_to_websocket(self, websocket, text: str):
        """
        生成TTS并发送给WebSocket客户端
        
        Args:
            websocket: WebSocket连接
            text: 要合成的文本
        """
        if not self.tts:
            return
        
        try:
            audio_data = b''
            async for chunk in self.tts.tts_stream(
                text=text,
                speed=self._cfg().minimax_tts.speed,
                volume=self._cfg().minimax_tts.volume,
                pitch=self._cfg().minimax_tts.pitch,
                sample_rate=self._cfg().minimax_tts.sample_rate,
                format=self._cfg().minimax_tts.format
            ):
                audio_data += chunk
            
            logger.info(f"TTS音频生成完成，总大小: {len(audio_data)} 字节")
            
            if audio_data and self.websocket_handler:
                logger.info(f"正在发送音频给客户端...")
                await self.websocket_handler.send_audio_to_client(websocket, audio_data, text)
                logger.info(f"音频发送完成")
            elif not audio_data:
                logger.warning(f"音频数据为空，跳过发送")
            elif not self.websocket_handler:
                logger.warning(f"websocket_handler 为空，无法发送音频")
            
        except Exception as e:
            logger.error(f"生成并发送TTS错误: {e}")
    
    async def _on_websocket_client_connected(self, websocket):
        """
        WebSocket客户端连接回调
        
        Args:
            websocket: WebSocket连接
        """
        logger.info(f"客户端 {websocket.remote_address} 已连接")
    
    async def _on_websocket_client_disconnected(self, websocket):
        """
        WebSocket客户端断开回调
        
        Args:
            websocket: WebSocket连接
        """
        try:
            if hasattr(websocket, 'asr') and websocket.asr:
                await websocket.asr.close()
            
            logger.info(f"客户端 {websocket.remote_address} 已断开")
        except Exception as e:
            logger.error(f"处理客户端断开错误: {e}")
    
    async def _on_websocket_stop_call(self, websocket):
        """
        WebSocket结束连麦回调
        
        Args:
            websocket: WebSocket连接
        """
        try:
            if hasattr(websocket, 'asr') and websocket.asr:
                await websocket.asr.close()
                websocket.asr = None
            
            logger.info(f"客户端 {websocket.remote_address} 结束连麦，准备停止WebSocket服务")
            
            if hasattr(websocket, 'history_manager') and websocket.history_manager:
                await self._save_conversation_memory(websocket.history_manager, self.user_nickname)
            
            asyncio.create_task(self._stop_service_async())
            
        except Exception as e:
            logger.error(f"处理结束连麦错误: {e}")
    
    async def _save_conversation_memory(self, history_manager: HistoryManager, user_nickname: str = ""):
        """
        保存对话记忆到booku_memory
        
        Args:
            history_manager: 历史记录管理器
            user_nickname: 用户昵称
        """
        try:
            if history_manager.is_empty():
                logger.info("对话历史为空，跳过保存记忆")
                return
            
            conversation_text = history_manager.format_for_llm()
            if len(conversation_text) < 50:
                logger.info("对话内容太短，跳过保存记忆")
                return
            
            summary = await self._summarize_conversation(conversation_text, user_nickname)
            if not summary:
                logger.warning("对话总结失败，跳过保存记忆")
                return
            
            await self._write_to_booku_memory(summary, user_nickname)
            
        except Exception as e:
            logger.error(f"保存对话记忆失败: {e}")
    
    async def _summarize_conversation(self, conversation_text: str, user_nickname: str = "") -> str:
        """
        总结对话内容
        
        Args:
            conversation_text: 对话文本
            user_nickname: 用户昵称
            
        Returns:
            str: 总结文本
        """
        try:
            user_label = f"与{user_nickname}" if user_nickname else "与用户"
            
            prompt = f"""请将以下语音对话记录总结为简洁的记忆条目，用于长期记忆存储。

对话记录：
{conversation_text}

要求：
1. 总结为1-3句话，突出重要信息（情感、事件、关系变化等）
2. 使用第三人称描述，如"辞安和{user_nickname if user_nickname else '用户'}..."
3. 保留关键细节（时间、地点、事件、情感）
4. 如果只是闲聊无重要信息，返回"无重要记忆点"

请直接输出总结内容："""

            response = await self.llm_client.generate(prompt, max_tokens=200)
            return response.strip() if response else ""
            
        except Exception as e:
            logger.error(f"总结对话失败: {e}")
            return ""
    
    async def _write_to_booku_memory(self, summary: str, user_nickname: str = ""):
        """
        写入booku_memory
        
        Args:
            summary: 总结内容
            user_nickname: 用户昵称
        """
        try:
            from src.app.plugin_system.api.llm_api import get_model_set_by_task, create_embedding_request
            
            model_set = get_model_set_by_task("embedding")
            if not model_set:
                logger.warning("未配置embedding模型，跳过向量存储")
                self._save_memory_to_file(summary, user_nickname)
                return
            
            embedding_request = create_embedding_request(model_set, inputs=[summary])
            embeddings = await embedding_request.execute()
            
            if not embeddings or not embeddings[0]:
                logger.warning("生成embedding失败，保存到文件")
                self._save_memory_to_file(summary, user_nickname)
                return
            
            from src.kernel.vector_db import get_vector_db_service
            vector_db = get_vector_db_service()
            
            import time
            memory_id = f"telme_{int(time.time() * 1000)}"
            
            metadata = {
                "source": "neo_tel_me",
                "user_nickname": user_nickname,
                "timestamp": time.time()
            }
            
            vector_db.add(
                collection_name="conversation_memories",
                ids=[memory_id],
                embeddings=[embeddings[0]],
                metadatas=[metadata],
                documents=[summary]
            )
            
            logger.info(f"[OK] 对话记忆已保存到向量库: {summary[:50]}...")
            
        except Exception as e:
            logger.error(f"写入向量库失败: {e}")
            self._save_memory_to_file(summary, user_nickname)
    
    def _save_memory_to_file(self, summary: str, user_nickname: str = ""):
        """
        备用：保存记忆到文件
        
        Args:
            summary: 总结内容
            user_nickname: 用户昵称
        """
        try:
            from datetime import datetime
            
            memory_file = DATA_DIR / "conversation_memories.json"
            memories = []
            
            if memory_file.exists():
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memories = json.load(f)
            
            memories.append({
                "timestamp": datetime.now().isoformat(),
                "user_nickname": user_nickname,
                "summary": summary
            })
            
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[OK] 对话记忆已保存到文件: {summary[:50]}...")
            
        except Exception as e:
            logger.error(f"保存记忆到文件失败: {e}")
    
    async def _stop_service_async(self):
        """
        异步停止服务
        """
        try:
            await asyncio.sleep(0.5)
            await self.stop()
            logger.info("WebSocket服务已停止，需要通过QQ重新触发才能连麦")
        except Exception as e:
            logger.error(f"停止服务错误: {e}")