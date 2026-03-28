import asyncio
import websockets
import json
import base64
from typing import Dict, Set, Callable, Optional


class WebSocketHandler:
    """
    WebSocket 处理器：处理 H5 页面的连麦请求
    """
    
    def __init__(self, config):
        """
        初始化 WebSocket 处理器
        
        Args:
            config: 插件配置
        """
        self.config = config
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.client_data: Dict[websockets.WebSocketServerProtocol, Dict] = {}
        self.server = None
        self.is_running = False
        
        # 回调函数
        self.on_audio_data: Optional[Callable] = None
        self.on_asr_result: Optional[Callable] = None
        self.on_client_connected: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None
    
    async def start(self):
        """
        启动 WebSocket 服务器
        """
        try:
            if not self.config.websocket_enabled:
                print("WebSocket 模式未启用")
                return
            
            # 启动 WebSocket 服务器
            self.server = await websockets.serve(
                self.handle_client,
                self.config.websocket_host,
                self.config.websocket_port
            )
            
            self.is_running = True
            print(f"🎙️ WebSocket 服务器已启动，监听 {self.config.websocket_host}:{self.config.websocket_port}")
            
            # 保持运行
            await self.server.wait_closed()
            
        except Exception as e:
            print(f"WebSocket 服务器启动失败: {e}")
            self.is_running = False
    
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
            'session_id': None
        }
        
        print(f"👤 客户端已连接: {websocket.remote_address}")
        
        # 调用客户端连接回调
        if self.on_client_connected:
            await self.on_client_connected(websocket)
        
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
            if not client_info['is_connected']:
                return
            
            # 解码音频数据
            audio_data = base64.b64decode(audio_base64)
            
            # 调用音频数据回调
            if self.on_audio_data:
                await self.on_audio_data(websocket, audio_data)
            
        except Exception as e:
            print(f"处理音频数据错误: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'处理音频数据错误: {str(e)}'
            }))
    
    async def send_audio_to_client(self, websocket: websockets.WebSocketServerProtocol, audio_data: bytes, text: str = ""):
        """
        发送音频数据到客户端
        
        Args:
            websocket: WebSocket 连接
            audio_data: 音频数据
            text: 文本内容
        """
        try:
            # 转换为 Base64
            audio_base64 = base64.b64encode(audio_data).decode()
            
            # 发送消息
            await websocket.send(json.dumps({
                'type': 'ai_message',
                'content': text,
                'audio': audio_base64
            }))
            
        except Exception as e:
            print(f"发送音频数据错误: {e}")
    
    async def send_message_to_client(self, websocket: websockets.WebSocketServerProtocol, message_type: str, content: str):
        """
        发送消息到客户端
        
        Args:
            websocket: WebSocket 连接
            message_type: 消息类型
            content: 消息内容
        """
        try:
            await websocket.send(json.dumps({
                'type': message_type,
                'content': content
            }))
        except Exception as e:
            print(f"发送消息错误: {e}")
    
    async def broadcast_to_all(self, message_type: str, content: str):
        """
        广播消息到所有客户端
        
        Args:
            message_type: 消息类型
            content: 消息内容
        """
        try:
            for websocket in self.clients:
                await self.send_message_to_client(websocket, message_type, content)
        except Exception as e:
            print(f"广播消息错误: {e}")
    
    def _cleanup_client(self, websocket: websockets.WebSocketServerProtocol):
        """
        清理客户端资源
        
        Args:
            websocket: WebSocket 连接
        """
        if websocket in self.clients:
            self.clients.remove(websocket)
        
        if websocket in self.client_data:
            del self.client_data[websocket]
        
        # 调用客户端断开回调
        if self.on_client_disconnected:
            asyncio.create_task(self.on_client_disconnected(websocket))
    
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
    
    def get_client_count(self) -> int:
        """
        获取连接的客户端数量
        
        Returns:
            int: 客户端数量
        """
        return len(self.clients)
