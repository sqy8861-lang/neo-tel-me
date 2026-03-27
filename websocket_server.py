import asyncio
import websockets
import json
import base64
import wave
import io
import threading
from typing import Dict, Set

from .aliyun_asr import AliyunRealtimeASR
from .minimax_tts import MiniMaxTTS
from .llm_client import LLMClient
from .llm_config import LLMConfig
from .history_manager import HistoryManager

class WebSocketServer:
    """
    WebSocket 服务器：处理 H5 页面的连麦请求
    """
    
    def __init__(self, config):
        """
        初始化 WebSocket 服务器
        
        Args:
            config: 插件配置
        """
        self.config = config
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.client_data: Dict[websockets.WebSocketServerProtocol, Dict] = {}
        self.server = None
        self.is_running = False
        
        # 服务组件
        self.asr = None
        self.tts = None
        self.llm_client = None
        self.history_manager = None
        
    async def start(self, host="0.0.0.0", port=8765):
        """
        启动 WebSocket 服务器
        
        Args:
            host: 主机地址
            port: 端口
        """
        try:
            # 初始化服务组件
            await self._initialize_services()
            
            # 启动 WebSocket 服务器
            self.server = await websockets.serve(
                self.handle_client,
                host,
                port
            )
            
            self.is_running = True
            print(f"🎙️ WebSocket 服务器已启动，监听 {host}:{port}")
            
            # 保持运行
            await self.server.wait_closed()
            
        except Exception as e:
            print(f"WebSocket 服务器启动失败: {e}")
            self.is_running = False
    
    async def _initialize_services(self):
        """
        初始化服务组件
        """
        try:
            # 初始化 LLM 配置和客户端
            llm_config = LLMConfig.load_from_core_config()
            self.llm_client = LLMClient(llm_config)
            await self.llm_client.initialize()
            
            # 初始化阿里云 ASR
            self.asr = AliyunRealtimeASR(
                appkey=self.config.aliyun_asr.appkey,
                access_key_id=self.config.aliyun_asr.access_key_id,
                access_key_secret=self.config.aliyun_asr.access_key_secret,
                sample_rate=self.config.aliyun_asr.sample_rate,
                format=self.config.aliyun_asr.format
            )
            
            # 初始化 MiniMax TTS
            self.tts = MiniMaxTTS(
                api_key=self.config.minimax_tts.api_key,
                voice_id=self.config.minimax_tts.voice_id,
                model=self.config.minimax_tts.model
            )
            
            print("✅ WebSocket 服务组件初始化完成")
        except Exception as e:
            print(f"服务组件初始化失败: {e}")
            raise
    
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """
        处理客户端连接
        
        Args:
            websocket: WebSocket 连接
        """
        # 添加客户端
        self.clients.add(websocket)
        self.client_data[websocket] = {
            'is_connected': False,
            'history_manager': HistoryManager(max_history=4),
            'asr': None,
            'current_tts_task': None
        }
        
        print(f"👤 客户端已连接: {websocket.remote_address}")
        
        try:
            # 发送初始化完成消息
            await websocket.send(json.dumps({
                'type': 'status',
                'status': 'ready',
                'message': '初始化完成，点击开始连麦'
            }))
            
            # 处理消息
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.ConnectionClosed:
            print(f"👤 客户端已断开: {websocket.remote_address}")
        except Exception as e:
            print(f"处理客户端消息错误: {e}")
        finally:
            # 清理客户端
            self._cleanup_client(websocket)
    
    async def handle_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """
        处理客户端消息
        
        Args:
            websocket: WebSocket 连接
            message: 消息内容
        """
        try:
            data = json.loads(message)
            client_info = self.client_data[websocket]
            
            if data['type'] == 'start_call':
                await self.start_call(websocket, client_info)
            
            elif data['type'] == 'stop_call':
                await self.stop_call(websocket, client_info)
            
            elif data['type'] == 'audio_data':
                await self.handle_audio_data(websocket, client_info, data['audio'])
            
        except Exception as e:
            print(f"处理消息错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'处理消息错误: {str(e)}'
            }))
    
    async def start_call(self, websocket: websockets.WebSocketServerProtocol, client_info: Dict):
        """
        开始连麦
        
        Args:
            websocket: WebSocket 连接
            client_info: 客户端信息
        """
        try:
            # 连接 ASR
            client_info['asr'] = AliyunRealtimeASR(
                appkey=self.config.aliyun_asr.appkey,
                access_key_id=self.config.aliyun_asr.access_key_id,
                access_key_secret=self.config.aliyun_asr.access_key_secret,
                sample_rate=self.config.aliyun_asr.sample_rate,
                format=self.config.aliyun_asr.format
            )
            
            connected = await client_info['asr'].connect(
                lambda text: self._on_asr_result(websocket, client_info, text)
            )
            
            if not connected:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'ASR 连接失败'
                }))
                return
            
            client_info['is_connected'] = True
            
            await websocket.send(json.dumps({
                'type': 'status',
                'status': 'connected',
                'message': '连麦中...'
            }))
            
            print(f"🎙️ 客户端 {websocket.remote_address} 开始连麦")
            
        except Exception as e:
            print(f"开始连麦错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'开始连麦错误: {str(e)}'
            }))
    
    async def stop_call(self, websocket: websockets.WebSocketServerProtocol, client_info: Dict):
        """
        结束连麦
        
        Args:
            websocket: WebSocket 连接
            client_info: 客户端信息
        """
        try:
            # 关闭 ASR 连接
            if client_info['asr']:
                await client_info['asr'].close()
                client_info['asr'] = None
            
            # 取消当前 TTS 任务
            if client_info['current_tts_task']:
                client_info['current_tts_task'].cancel()
                try:
                    await client_info['current_tts_task']
                except asyncio.CancelledError:
                    pass
                client_info['current_tts_task'] = None
            
            client_info['is_connected'] = False
            
            await websocket.send(json.dumps({
                'type': 'status',
                'status': 'ready',
                'message': '连麦已结束'
            }))
            
            print(f"🛑 客户端 {websocket.remote_address} 结束连麦")
            
        except Exception as e:
            print(f"结束连麦错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'结束连麦错误: {str(e)}'
            }))
    
    async def handle_audio_data(self, websocket: websockets.WebSocketServerProtocol, client_info: Dict, audio_base64: str):
        """
        处理音频数据
        
        Args:
            websocket: WebSocket 连接
            client_info: 客户端信息
            audio_base64: Base64 编码的音频数据
        """
        try:
            if not client_info['is_connected'] or not client_info['asr']:
                return
            
            # 解码音频数据
            audio_data = base64.b64decode(audio_base64)
            
            # 发送到 ASR
            await client_info['asr'].send_audio(audio_data)
            
        except Exception as e:
            print(f"处理音频数据错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'处理音频数据错误: {str(e)}'
            }))
    
    async def _on_asr_result(self, websocket: websockets.WebSocketServerProtocol, client_info: Dict, text: str):
        """
        ASR 识别结果回调
        
        Args:
            websocket: WebSocket 连接
            client_info: 客户端信息
            text: 识别文本
        """
        try:
            print(f"👤 用户说: {text}")
            
            # 添加用户消息到历史记录
            client_info['history_manager'].add_user_message(text)
            
            # 生成回复
            reply = await self._generate_reply(client_info, text)
            print(f"🤖 AI 说: {reply}")
            
            # 添加 AI 回复到历史记录
            client_info['history_manager'].add_assistant_message(reply)
            
            # 生成 TTS
            audio_data = await self._generate_tts(reply)
            
            # 发送 AI 回复和音频
            await websocket.send(json.dumps({
                'type': 'ai_message',
                'content': reply,
                'audio': audio_data
            }))
            
        except Exception as e:
            print(f"处理 ASR 结果错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'处理语音识别结果错误: {str(e)}'
            }))
    
    async def _generate_reply(self, client_info: Dict, text: str) -> str:
        """
        生成 AI 回复
        
        Args:
            client_info: 客户端信息
            text: 用户输入文本
            
        Returns:
            str: AI 回复
        """
        try:
            # 获取历史记录
            history_text = client_info['history_manager'].format_for_llm()
            
            # 使用 LLM 生成回复
            reply = await self.llm_client.generate_response(text, history_text)
            
            if reply:
                return reply
            else:
                print("LLM 返回空回复，使用模拟回复")
                return self._get_mock_reply(text)
                
        except Exception as e:
            print(f"生成回复错误: {e}")
            return self._get_mock_reply(text)
    
    def _get_mock_reply(self, text: str) -> str:
        """
        获取模拟回复
        
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
    
    async def _generate_tts(self, text: str) -> str:
        """
        生成 TTS 音频
        
        Args:
            text: 要合成的文本
            
        Returns:
            str: Base64 编码的音频数据
        """
        try:
            # 生成 TTS
            audio_data = b''
            async for chunk in self.tts.tts_stream(
                text=text,
                speed=self.config.minimax_tts.speed,
                volume=self.config.minimax_tts.volume,
                pitch=self.config.minimax_tts.pitch,
                sample_rate=self.config.minimax_tts.sample_rate
            ):
                audio_data += chunk
            
            # 转换为 Base64
            return base64.b64encode(audio_data).decode()
            
        except Exception as e:
            print(f"生成 TTS 错误: {e}")
            # 返回空音频
            return ""
    
    def _cleanup_client(self, websocket: websockets.WebSocketServerProtocol):
        """
        清理客户端资源
        
        Args:
            websocket: WebSocket 连接
        """
        if websocket in self.clients:
            self.clients.remove(websocket)
        
        if websocket in self.client_data:
            client_info = self.client_data[websocket]
            
            # 关闭 ASR 连接
            if client_info.get('asr'):
                asyncio.create_task(client_info['asr'].close())
            
            # 取消 TTS 任务
            if client_info.get('current_tts_task'):
                client_info['current_tts_task'].cancel()
            
            del self.client_data[websocket]
    
    async def stop(self):
        """
        停止 WebSocket 服务器
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # 清理所有客户端
        for websocket in list(self.clients):
            try:
                await websocket.close()
            except:
                pass
        
        self.clients.clear()
        self.client_data.clear()
        self.is_running = False
        
        print("🛑 WebSocket 服务器已停止")

    def is_service_running(self) -> bool:
        """
        检查服务是否运行
        
        Returns:
            bool: 服务是否运行
        """
        return self.is_running