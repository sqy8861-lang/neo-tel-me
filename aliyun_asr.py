import asyncio
import websockets
import json
import base64
import uuid
from urllib.parse import urlencode
from typing import Optional, Callable


class AliyunRealtimeASR:
    """
    阿里云实时语音识别 WebSocket 客户端
    """
    
    def __init__(self, appkey: str, sample_rate: int = 16000, format: str = "pcm"):
        """
        初始化阿里云ASR客户端
        
        Args:
            appkey: 阿里云AppKey
            sample_rate: 采样率
            format: 音频格式
        """
        self.appkey = appkey
        self.sample_rate = sample_rate
        self.format = format
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.on_result: Optional[Callable] = None  # 回调函数
        self.connected = False
        
    def generate_auth_url(self) -> str:
        """
        生成阿里云 WebSocket 认证 URL
        
        Returns:
            str: 认证URL
        """
        url = "wss://nls-gateway.aliyuncs.com/ws/v1"
        token = "default"  # 使用 token 模式，简化签名
        
        # 构建请求参数
        params = {
            "appkey": self.appkey,
            "token": token,
            "format": self.format,
            "sample_rate": str(self.sample_rate),
            "enable_intermediate_result": "true",  # 返回中间结果
            "enable_punctuation_prediction": "true",  # 标点预测
            "enable_inverse_text_normalization": "true",  # ITN
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
        
        headers = {
            "X-NLS-Token": "default",  # 实际生产环境建议用 Token 服务
        }
        
        try:
            self.ws = await websockets.connect(uri, extra_headers=headers)
            self.connected = True
            print("✅ 阿里云 ASR 已连接")
            
            # 启动接收任务
            asyncio.create_task(self._receive_loop())
            return True
        except Exception as e:
            print(f"❌ 阿里云 ASR 连接失败: {e}")
            return False
    
    async def _receive_loop(self):
        """
        接收 ASR 结果
        """
        try:
            async for message in self.ws:
                result = json.loads(message)
                
                # 处理识别结果
                if result.get("header", {}).get("name") == "TranscriptionResultChanged":
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
        if not self.connected or not self.ws:
            return False
            
        # 阿里云要求 base64 编码的音频数据
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "namespace": "SpeechTranscriber",
                "name": "RunAudioTranscription",
                "appkey": self.appkey
            },
            "payload": {
                "audio": audio_base64,
                "sample_rate": self.sample_rate,
                "format": self.format
            }
        }
        
        try:
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False
        
    async def close(self):
        """
        关闭连接
        """
        if self.ws:
            await self.ws.close()
            self.connected = False
            print("🔌 阿里云 ASR 连接已关闭")