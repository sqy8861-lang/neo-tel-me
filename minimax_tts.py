import asyncio
import websockets
import json
import ssl
import os
import time
from typing import Optional


class MiniMaxTTS:
    def __init__(self, api_key, voice_id, model="speech-2.8-hd"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.is_playing_flag = False
        self.current_task = None
        
        # 连接池管理
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.last_activity_time = 0
        self.connection_lock = asyncio.Lock()
        self.task_lock = asyncio.Lock()
        
        # 心跳检测配置
        self.heartbeat_interval = 30
        self.connection_timeout = 300
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def _ensure_connection(self):
        """
        确保WebSocket连接可用
        
        Returns:
            bool: 连接是否成功
        """
        async with self.connection_lock:
            # 检查现有连接是否可用
            if self.websocket and self.is_connected:
                try:
                    # 发送ping检测连接是否存活
                    await self.websocket.ping()
                    self.last_activity_time = time.time()
                    return True
                except Exception as e:
                    print(f"连接检测失败: {e}")
                    await self._close_connection_internal()
            
            # 建立新连接
            try:
                url = "wss://api.minimax.io/ws/v1/t2a_v2"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                print(f"正在建立TTS连接: {url}")
                self.websocket = await websockets.connect(
                    url, 
                    additional_headers=headers, 
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=10
                )
                
                # 等待连接确认
                connected = json.loads(await self.websocket.recv())
                print(f"TTS连接响应: {json.dumps(connected, ensure_ascii=False)}")
                
                if connected.get("event") == "connected_success":
                    self.is_connected = True
                    self.last_activity_time = time.time()
                    
                    # 启动心跳检测
                    if not self.heartbeat_task or self.heartbeat_task.done():
                        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    
                    print("✅ TTS连接建立成功")
                    return True
                else:
                    print(f"❌ TTS连接失败: {connected}")
                    await self._close_connection_internal()
                    return False
                    
            except Exception as e:
                print(f"❌ 建立TTS连接失败: {e}")
                await self._close_connection_internal()
                return False
    
    async def _heartbeat_loop(self):
        """
        心跳检测循环
        """
        try:
            while self.is_connected and self.websocket:
                await asyncio.sleep(self.heartbeat_interval)
                
                # 检查连接是否超时
                if time.time() - self.last_activity_time > self.connection_timeout:
                    print("TTS连接超时，准备关闭")
                    await self._close_connection_internal()
                    break
                
                # 发送心跳
                try:
                    if self.websocket and self.is_connected:
                        await self.websocket.ping()
                        print("💓 TTS心跳检测")
                except Exception as e:
                    print(f"TTS心跳失败: {e}")
                    await self._close_connection_internal()
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"心跳循环异常: {e}")
    
    async def _close_connection_internal(self):
        """
        内部关闭连接方法（不加锁）
        """
        try:
            if self.websocket:
                try:
                    await self.websocket.send(json.dumps({"event": "task_finish"}))
                    await asyncio.sleep(0.1)
                    await self.websocket.close()
                except Exception:
                    pass
        finally:
            self.websocket = None
            self.is_connected = False
            print("🔌 TTS连接已关闭")
    
    async def tts_stream(self, text, speed=1, volume=1, pitch=0, sample_rate=32000, format="mp3"):
        """
        生成TTS音频流（使用连接复用）
        
        Args:
            text: 要合成的文本
            speed: 语速，范围 [0.5, 2]
            volume: 音量，范围 (0, 10]
            pitch: 音调，范围 [-12, 12]，整数
            sample_rate: 采样率，支持 [8000, 16000, 22050, 24000, 32000, 44100]
            format: 音频格式，支持 [mp3, pcm, flac, wav]
            
        Yields:
            bytes: 音频数据块
        """
        if not isinstance(pitch, int):
            pitch = int(pitch)
        pitch = max(-12, min(12, pitch))
        
        speed = max(0.5, min(2.0, speed))
        volume = max(0.01, min(10.0, volume))
        
        async with self.task_lock:
            self.is_playing_flag = True
            
            try:
                if not await self._ensure_connection():
                    print("[FAIL] 无法建立TTS连接")
                    yield b""
                    return
                
                if not await self._start_task(speed, volume, pitch, sample_rate, format):
                    print("[FAIL] TTS任务启动失败")
                    await self._close_connection_internal()
                    if not await self._ensure_connection():
                        yield b""
                        return
                    
                    if not await self._start_task(speed, volume, pitch, sample_rate, format):
                        print("[FAIL] TTS任务重试失败")
                        yield b""
                        return
                
                print(f"发送文本: {text}")
                await self.websocket.send(json.dumps({
                    "event": "task_continue",
                    "text": text
                }))
                
                while True:
                    try:
                        response = json.loads(await self.websocket.recv())
                        
                        if "data" in response and "audio" in response["data"]:
                            audio = response["data"]["audio"]
                            if audio:
                                try:
                                    audio_bytes = bytes.fromhex(audio)
                                    self.last_activity_time = time.time()
                                    yield audio_bytes
                                except Exception as e:
                                    print(f"转换音频数据失败: {e}")
                        
                        if response.get("is_final"):
                            print("[OK] TTS合成完成")
                            break
                            
                    except websockets.ConnectionClosed:
                        print("[WARN] TTS连接被关闭")
                        await self._close_connection_internal()
                        yield b""
                        return
                    except Exception as e:
                        print(f"TTS流处理错误: {e}")
                        break
                        
            except Exception as e:
                print(f"TTS合成异常: {e}")
            finally:
                self.is_playing_flag = False
                self.current_task = None
    
    async def _start_task(self, speed, volume, pitch, sample_rate, format):
        """
        发送任务开始请求
        
        Args:
            speed: 语速
            volume: 音量
            pitch: 音调
            sample_rate: 采样率
            format: 音频格式
            
        Returns:
            bool: 任务是否启动成功
        """
        if not self.websocket or not self.is_connected:
            return False
        
        try:
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
            
            print(f"发送TTS任务开始请求: model={self.model}, voice_id={self.voice_id}, sample_rate={sample_rate}, format={format}")
            await self.websocket.send(json.dumps(start_msg))
            
            response = json.loads(await self.websocket.recv())
            print(f"TTS任务响应: {json.dumps(response, ensure_ascii=False)}")
            
            success = response.get("event") == "task_started"
            if success:
                self.last_activity_time = time.time()
            else:
                print(f"TTS任务失败原因: {response}")
            
            return success
            
        except Exception as e:
            print(f"启动TTS任务失败: {e}")
            return False
    
    def is_playing(self):
        """
        检查是否正在播放
        
        Returns:
            bool: 是否正在播放
        """
        return self.is_playing_flag
    
    def interrupt(self):
        """
        打断播放
        """
        self.is_playing_flag = False
        if self.current_task:
            self.current_task.cancel()
    
    async def close(self):
        """
        关闭连接（服务停止时调用）
        """
        # 停止心跳任务
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭连接
        await self._close_connection_internal()
