import asyncio
import websockets
import json
import base64
import os
import ssl
import ipaddress
from pathlib import Path
from typing import Dict, Set, Callable, Optional
from src.kernel.logger import get_logger
from websockets.http11 import Response
from websockets.datastructures import Headers

logger = get_logger("neo_tel_me")


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
        self.on_stop_call: Optional[Callable] = None
    
    async def start(self):
        """
        启动 WebSocket 服务器和静态文件服务
        """
        try:
            if not self.config.websocket.enabled:
                logger.info("WebSocket 模式未启用")
                return
            
            # 确定静态文件目录
            current_dir = Path(__file__).parent
            self.web_dir = current_dir / "web"
            
            # 准备SSL上下文
            ssl_context = None
            if self.config.websocket.use_ssl:
                ssl_context = self._create_ssl_context()
                if ssl_context:
                    logger.info("🔒 SSL/TLS 已启用（HTTPS/WSS）")
                else:
                    logger.warning("⚠️ SSL配置失败，将使用HTTP/WS")
            
            # 启动 WebSocket 服务器
            self.server = await websockets.serve(
                self.handle_client,
                self.config.websocket.host,
                self.config.websocket.port,
                process_request=self.process_request,
                ssl=ssl_context
            )
            
            self.is_running = True
            protocol = "HTTPS/WSS" if ssl_context else "HTTP/WS"
            logger.info(f"🎙️ WebSocket 服务器已启动，监听 {self.config.websocket.host}:{self.config.websocket.port} ({protocol})")
            logger.info(f"📁 静态文件服务已启动，目录: {self.web_dir}")
            
            # 保持运行
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"WebSocket 服务器启动失败: {e}")
            self.is_running = False
    
    def _create_ssl_context(self):
        """
        创建SSL上下文
        
        Returns:
            ssl.SSLContext: SSL上下文对象，如果配置失败则返回None
        """
        try:
            cert_path = self.config.websocket.ssl_cert
            key_path = self.config.websocket.ssl_key
            
            # 如果没有配置证书路径，尝试生成自签名证书
            if not cert_path or not key_path:
                cert_path, key_path = self._generate_self_signed_cert()
                if not cert_path or not key_path:
                    logger.error("❌ 无法生成自签名证书")
                    return None
            
            # 检查证书文件是否存在
            if not Path(cert_path).exists():
                logger.error(f"❌ SSL证书文件不存在: {cert_path}")
                return None
            
            if not Path(key_path).exists():
                logger.error(f"❌ SSL私钥文件不存在: {key_path}")
                return None
            
            # 创建SSL上下文
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert_path, key_path)
            
            logger.info(f"✅ SSL证书加载成功: {cert_path}")
            return ssl_context
            
        except Exception as e:
            logger.error(f"创建SSL上下文失败: {e}")
            return None
    
    def _generate_self_signed_cert(self):
        """
        生成自签名SSL证书
        
        Returns:
            tuple: (证书路径, 私钥路径)，如果失败则返回(None, None)
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime
            
            # 证书存储目录
            cert_dir = Path(__file__).parent / "ssl"
            cert_dir.mkdir(exist_ok=True)
            
            cert_path = cert_dir / "cert.pem"
            key_path = cert_dir / "key.pem"
            
            # 如果证书已存在，直接返回
            if cert_path.exists() and key_path.exists():
                logger.info(f"✅ 使用已存在的自签名证书: {cert_path}")
                return str(cert_path), str(key_path)
            
            logger.info("🔐 正在生成自签名SSL证书...")
            
            # 生成私钥
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # 生成证书
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Neo-MoFox"),
                x509.NameAttribute(NameOID.COMMON_NAME, self.config.websocket.public_ip or self.config.websocket.host),
            ])
            
            cert = (x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
                .add_extension(
                    x509.SubjectAlternativeName([
                        x509.DNSName(self.config.websocket.public_ip or self.config.websocket.host),
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    ]),
                    critical=False,
                )
                .sign(key, hashes.SHA256()))
            
            # 保存私钥
            with open(key_path, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            
            # 保存证书
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            logger.info(f"✅ 自签名证书生成成功: {cert_path}")
            logger.info("⚠️ 注意：自签名证书在浏览器中会显示不安全警告，但可以正常使用")
            
            return str(cert_path), str(key_path)
            
        except ImportError:
            logger.error("❌ 缺少cryptography库，无法生成自签名证书")
            logger.error("请安装: pip install cryptography")
            return None, None
        except Exception as e:
            logger.error(f"生成自签名证书失败: {e}")
            return None, None
    
    async def process_request(self, connection, request):
        """
        处理 HTTP 请求，提供静态文件
        
        Args:
            connection: ServerConnection 对象
            request: Request 对象
            
        Returns:
            如果是 HTTP 请求，返回 HTTP 响应
            如果是 WebSocket 连接请求，返回 None
        """
        # 检查是否是 WebSocket 连接请求
        if "upgrade" in request.headers.get("connection", "").lower():
            # 是 WebSocket 连接请求，交给 websockets 库处理
            return None
        
        # 是 HTTP 请求，提供静态文件
        try:
            # 处理路径 - 安全检查，防止路径遍历攻击
            path = request.path.split("?")[0]  # 移除查询参数
            if path == "/":
                file_path = self.web_dir / "index.html"
            else:
                # 移除开头的斜杠并安全地构建路径
                safe_path = path.lstrip("/")
                # 防止路径遍历攻击
                if ".." in safe_path or safe_path.startswith("/"):
                    headers = Headers([("Content-Type", "text/plain"), ("Content-Length", "9")])
                    return Response(403, "Forbidden", headers, b"Forbidden")
                file_path = self.web_dir / safe_path
            
            # 检查文件是否存在且在 web_dir 目录内
            try:
                file_path = file_path.resolve()
                if not str(file_path).startswith(str(self.web_dir.resolve())):
                    headers = Headers([("Content-Type", "text/plain"), ("Content-Length", "9")])
                    return Response(403, "Forbidden", headers, b"Forbidden")
            except Exception:
                headers = Headers([("Content-Type", "text/plain"), ("Content-Length", "9")])
                return Response(404, "Not Found", headers, b"Not Found")
            
            if not file_path.exists() or not file_path.is_file():
                headers = Headers([("Content-Type", "text/plain"), ("Content-Length", "9")])
                return Response(404, "Not Found", headers, b"Not Found")
            
            # 读取文件内容
            with open(file_path, "rb") as f:
                content = f.read()
            
            # 设置 Content-Type
            if file_path.suffix == ".html":
                content_type = "text/html"
            elif file_path.suffix == ".css":
                content_type = "text/css"
            elif file_path.suffix == ".js":
                content_type = "application/javascript"
            else:
                content_type = "application/octet-stream"
            
            # 返回 HTTP 响应
            headers = Headers([
                ("Content-Type", content_type),
                ("Content-Length", str(len(content)))
            ])
            return Response(200, "OK", headers, content)
            
        except Exception as e:
            logger.error(f"处理静态文件请求失败: {e}")
            headers = Headers([("Content-Type", "text/plain"), ("Content-Length", "21")])
            return Response(500, "Internal Server Error", headers, b"Internal Server Error")
    
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
        
        logger.info(f"👤 客户端已连接: {websocket.remote_address}")
        
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
            logger.info(f"👤 客户端已断开: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"处理客户端消息错误: {e}")
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
            logger.error(f"处理消息错误: {e}")
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
            
            logger.info(f"🎙️ 客户端 {websocket.remote_address} 开始连麦")
            
        except Exception as e:
            logger.error(f"开始连麦错误: {e}")
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
            
            if self.on_stop_call:
                await self.on_stop_call(websocket)
            
            await websocket.send(json.dumps({
                'type': 'status',
                'status': 'ready',
                'message': '连麦已结束'
            }))
            
            logger.info(f"[STOP] 客户端 {websocket.remote_address} 结束连麦")
            
        except Exception as e:
            logger.error(f"结束连麦错误: {e}")
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
            logger.error(f"处理音频数据错误: {e}")
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
            logger.info(f"send_audio_to_client: 音频大小={len(audio_data)}字节, 文本长度={len(text)}")
            
            audio_base64 = base64.b64encode(audio_data).decode()
            logger.info(f"Base64编码完成，长度={len(audio_base64)}")
            
            message = json.dumps({
                'type': 'ai_message',
                'content': text,
                'audio': audio_base64
            })
            logger.info(f"JSON消息构建完成，长度={len(message)}")
            
            await websocket.send(message)
            logger.info(f"音频消息已发送给客户端 {websocket.remote_address}")
            
        except Exception as e:
            logger.error(f"发送音频数据错误: {e}")
    
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
            logger.error(f"发送消息错误: {e}")
    
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
            logger.error(f"广播消息错误: {e}")
    
    def _cleanup_client(self, websocket):
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
            try:
                asyncio.create_task(self.on_client_disconnected(websocket))
            except RuntimeError:
                # 如果事件循环已经关闭，忽略错误
                pass
    
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
        
        logger.info("🛑 WebSocket 服务器已停止")
    
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
