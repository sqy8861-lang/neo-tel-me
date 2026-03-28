import asyncio
import websockets
import json
import ssl
import os

class MiniMaxTTS:
    def __init__(self, api_key, voice_id, model="speech-2.8-hd"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.is_playing_flag = False
        self.current_task = None
        self.current_websocket = None

    async def tts_stream(self, text, speed=1, volume=1, pitch=0, sample_rate=32000, format="mp3"):
        """生成TTS音频流"""
        self.is_playing_flag = True
        try:
            # 建立WebSocket连接
            ws = await self._establish_connection()
            if not ws:
                yield b""
                return

            self.current_websocket = ws

            # 开始任务
            if not await self._start_task(ws, speed, volume, pitch, sample_rate, format):
                await self._close_connection(ws)
                yield b""
                return

            # 发送文本并接收音频数据
            await ws.send(json.dumps({
                "event": "task_continue",
                "text": text
            }))

            while True:
                try:
                    response = json.loads(await ws.recv())

                    if "data" in response and "audio" in response["data"]:
                        audio = response["data"]["audio"]
                        if audio:
                            audio_bytes = bytes.fromhex(audio)
                            yield audio_bytes

                    if response.get("is_final"):
                        break

                except Exception as e:
                    print(f"TTS stream error: {e}")
                    break

        finally:
            if self.current_websocket:
                await self._close_connection(self.current_websocket)
            self.is_playing_flag = False
            self.current_task = None
            self.current_websocket = None

    async def _establish_connection(self):
        """建立WebSocket连接"""
        url = "wss://api.minimax.io/ws/v1/t2a_v2"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            ws = await websockets.connect(url, additional_headers=headers, ssl=ssl_context)
            connected = json.loads(await ws.recv())
            if connected.get("event") == "connected_success":
                return ws
            return None
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    async def _start_task(self, websocket, speed, volume, pitch, sample_rate, format):
        """发送任务开始请求"""
        start_msg = {
            "event": "task_start",
            "model": self.model,
            "voice_setting": {
                "voice_id": self.voice_id,
                "speed": speed,
                "vol": volume,
                "pitch": pitch,
                "english_normalization": False
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": 128000,
                "format": format,
                "channel": 1
            }
        }
        await websocket.send(json.dumps(start_msg))
        response = json.loads(await websocket.recv())
        return response.get("event") == "task_started"

    async def _close_connection(self, websocket):
        """关闭连接"""
        if websocket:
            try:
                await websocket.send(json.dumps({"event": "task_finish"}))
                await websocket.close()
            except Exception:
                pass

    def is_playing(self):
        """检查是否正在播放"""
        return self.is_playing_flag

    def interrupt(self):
        """打断播放"""
        self.is_playing_flag = False
        if self.current_task:
            self.current_task.cancel()
        if self.current_websocket:
            asyncio.create_task(self._close_connection(self.current_websocket))
