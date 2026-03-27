import asyncio
import websockets
import json
import base64
from typing import Optional


class MiniMaxTTS:
    """
    MiniMax TTS 客户端
    """
    
    def __init__(self, api_key: str, voice_id: str, model: str = "speech-2.8-hd"):
        """
        初始化MiniMax TTS客户端
        
        Args:
            api_key: MiniMax API密钥
            voice_id: 语音ID
            model: TTS模型
        """
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.base_url = "wss://api.minimax.com/ws/v1/t2a_v2"
        self.is_speaking = False
        self.interrupt_event = asyncio.Event()
        
    async def tts_stream(self, text: str, speed: float = 1.0, volume: float = 1.0, 
                         pitch: float = 0.0, sample_rate: int = 24000):
        """
        MiniMax TTS 流式播放（可被中断）
        
        Args:
            text: 要合成的文本
            speed: 语速
            volume: 音量
            pitch: 音调
            sample_rate: 采样率
            
        Yields:
            bytes: 音频数据
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with websockets.connect(self.base_url, extra_headers=headers) as ws:
                request = {
                    "model": self.model,
                    "text": text,
                    "stream": True,
                    "voice_setting": {
                        "voice_id": self.voice_id,
                        "speed": speed,
                        "vol": volume,
                        "pitch": pitch
                    },
                    "audio_setting": {
                        "sample_rate": sample_rate,
                        "format": "pcm"
                    }
                }
                
                await ws.send(json.dumps(request))
                
                self.is_speaking = True
                self.interrupt_event.clear()
                
                try:
                    async for message in ws:
                        # 检查打断信号
                        if self.interrupt_event.is_set():
                            print("🛑 TTS 被打断")
                            break
                        
                        resp = json.loads(message)
                        if resp.get("data", {}).get("audio"):
                            audio_data = base64.b64decode(resp["data"]["audio"])
                            # 这里返回音频数据，由调用方处理播放
                            yield audio_data
                        
                        if resp.get("data", {}).get("status") == "finished":
                            break
                            
                finally:
                    self.is_speaking = False
                    self.interrupt_event.clear()
        except Exception as e:
            print(f"TTS 错误: {e}")
            self.is_speaking = False
            self.interrupt_event.clear()
    
    def interrupt(self):
        """
        打断当前TTS播放
        """
        self.interrupt_event.set()
        print("👤 打断 TTS 播放")
    
    def is_playing(self) -> bool:
        """
        检查是否正在播放
        
        Returns:
            bool: 是否正在播放
        """
        return self.is_speaking