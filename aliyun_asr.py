import asyncio
import websockets
import json
import base64
import uuid
import hmac
import hashlib
import time
from urllib.parse import urlencode
from typing import Optional, Callable


class AliyunRealtimeASR:
    """
    阿里云实时语音识别 WebSocket 客户端
    """
    
    def __init__(self, appkey: str, access_key_id: str, access_key_secret: str, sample_rate: int = 16000, format: str = "pcm"):
        """
        初始化阿里云ASR客户端
        
        Args:
            appkey: 阿里云AppKey
            access_key_id: 阿里云AccessKeyId
            access_key_secret: 阿里云AccessKeySecret
            sample_rate: 采样率
            format: 音频格式
        """
        self.appkey = appkey
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sample_rate = sample_rate
        self.format = format
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.on_result: Optional[Callable] = None  # 回调函数
        self.connected = False
        self.task_id = str(uuid.uuid4()).replace('-', '')  # 32位唯一ID
        self.is_ready = False  # 是否准备就绪可以发送音频
        
    def generate_token(self) -> str:
        """
        生成阿里云认证Token
        
        Returns:
            str: 认证Token
        """
        # 生成时间戳
        timestamp = str(int(time.time()))
        # 生成签名
        signature_str = f"{self.access_key_id}\n{timestamp}"
        signature = hmac.new(
            self.access_key_secret.encode('utf-8'),
            signature_str.encode('utf-8'),
            hashlib.sha1
        ).digest()
        signature_base64 = base64.b64encode(signature).decode('utf-8')
        # 构建token
        token = f"{self.access_key_id}:{signature_base64}:{timestamp}"
        return token
    
    def generate_auth_url(self) -> str:
        """
        生成阿里云 WebSocket 认证 URL
        
        Returns:
            str: 认证URL
        """
        # 使用上海地域的WebSocket地址
        url = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
        token = self.generate_token()
        
        # 构建请求参数
        params = {
            "token": token
        }
        
        return f"{url}?{urlencode(params)}"
    
    async def connect(self, on_result_callback: Callable) -> bool:
        """
        连接阿里云 ASR WebSocket
        
        Args:
            on_result_callback: 识别结果回调函数
            
        Returns:
            bool: 连接是否成功
        """
        self.on_result = on_result_callback
        uri = self.generate_auth_url()
        
        try:
            self.ws = await websockets.connect(uri)
            self.connected = True
            print("✅ 阿里云 ASR 已连接")
            
            # 启动接收任务
            asyncio.create_task(self._receive_loop())
            
            # 发送StartTranscription指令
            await self._send_start_transcription()
            
            # 等待准备就绪
            for _ in range(10):
                if self.is_ready:
                    return True
                await asyncio.sleep(0.5)
            
            print("❌ 阿里云 ASR 准备超时")
            return False
        except Exception as e:
            print(f"❌ 阿里云 ASR 连接失败: {e}")
            return False
    
    async def _send_start_transcription(self):
        """
        发送StartTranscription指令
        """
        if not self.connected or not self.ws:
            return
        
        message_id = str(uuid.uuid4()).replace('-', '')  # 32位唯一ID
        
        message = {
            "header": {
                "message_id": message_id,
                "task_id": self.task_id,
                "namespace": "SpeechTranscriber",
                "name": "StartTranscription",
                "appkey": self.appkey
            },
            "payload": {
                "format": self.format,
                "sample_rate": self.sample_rate,
                "enable_intermediate_result": True,  # 返回中间结果
                "enable_punctuation_prediction": True,  # 标点预测
                "enable_inverse_text_normalization": True  # ITN
            }
        }
        
        try:
            await self.ws.send(json.dumps(message))
            print("📢 已发送 StartTranscription 指令")
        except Exception as e:
            print(f"发送 StartTranscription 指令失败: {e}")
    
    async def _receive_loop(self):
        """
        接收 ASR 结果
        """
        try:
            async for message in self.ws:
                result = json.loads(message)
                
                # 处理识别结果
                if result.get("header", {}).get("name") == "TranscriptionStarted":
                    # 服务端准备就绪
                    self.is_ready = True
                    print("✅ 阿里云 ASR 准备就绪，可以发送音频")
                    
                elif result.get("header", {}).get("name") == "TranscriptionResultChanged":
                    # 中间结果（说话过程中实时返回）
                    text = result["payload"]["result"]
                    print(f"📝 [识别中] {text}")
                    
                elif result.get("header", {}).get("name") == "SentenceEnd":
                    # 一句话结束（最终确认结果）
                    text = result["payload"]["result"]
                    print(f"✅ [识别完成] {text}")
                    if self.on_result:
                        await self.on_result(text)
                        
                elif result.get("header", {}).get("name") == "TranscriptionCompleted":
                    print("🎉 识别会话完成")
                
                elif result.get("header", {}).get("status") != 20000000:
                    # 错误信息
                    status_message = result.get("header", {}).get("status_message", "未知错误")
                    print(f"❌ 阿里云 ASR 错误: {status_message}")
                    
        except Exception as e:
            print(f"ASR 接收错误: {e}")
            self.connected = False
            
    async def send_audio(self, audio_bytes: bytes) -> bool:
        """
        发送音频数据到 ASR
        
        Args:
            audio_bytes: 音频数据
            
        Returns:
            bool: 发送是否成功
        """
        if not self.connected or not self.ws or not self.is_ready:
            return False
            
        try:
            # 使用二进制帧发送音频数据
            await self.ws.send(audio_bytes)
            return True
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False
    
    async def stop_transcription(self):
        """
        发送StopTranscription指令
        """
        if not self.connected or not self.ws:
            return
        
        message_id = str(uuid.uuid4()).replace('-', '')  # 32位唯一ID
        
        message = {
            "header": {
                "message_id": message_id,
                "task_id": self.task_id,
                "namespace": "SpeechTranscriber",
                "name": "StopTranscription",
                "appkey": self.appkey
            }
        }
        
        try:
            await self.ws.send(json.dumps(message))
            print("📢 已发送 StopTranscription 指令")
        except Exception as e:
            print(f"发送 StopTranscription 指令失败: {e}")
    
    async def close(self):
        """
        关闭连接
        """
        if self.ws:
            # 发送StopTranscription指令
            await self.stop_transcription()
            # 等待一段时间让服务端处理
            await asyncio.sleep(0.5)
            # 关闭WebSocket连接
            await self.ws.close()
            self.connected = False
            self.is_ready = False
            print("🔌 阿里云 ASR 连接已关闭")