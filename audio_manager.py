import pyaudio
import numpy as np
import threading
import asyncio
from typing import Optional, Callable


class AudioManager:
    """
    音频管理器：处理音频采集和播放
    """
    
    def __init__(self, sample_rate: int = 16000, chunk: int = 1024, 
                 vad_threshold: int = 800):
        """
        初始化音频管理器
        
        Args:
            sample_rate: 采样率
            chunk: 音频块大小
            vad_threshold: 语音活动检测阈值
        """
        self.sample_rate = sample_rate
        self.chunk = chunk
        self.vad_threshold = vad_threshold
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.is_recording = False
        self.is_playing = False
        self.audio_callback: Optional[Callable] = None
        self.vad_callback: Optional[Callable] = None
        self.loop = None
    
    def start_recording(self, audio_callback: Callable, 
                       vad_callback: Optional[Callable] = None):
        """
        开始音频采集
        
        Args:
            audio_callback: 音频数据回调函数
            vad_callback: 语音活动检测回调函数
        """
        self.audio_callback = audio_callback
        self.vad_callback = vad_callback
        self.loop = asyncio.get_event_loop()
        
        # 打开输入流
        self.input_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        
        self.is_recording = True
        print("🎤 麦克风已开启，开始说话...")
        
        # 启动采集线程
        self.record_thread = threading.Thread(target=self._record_loop)
        self.record_thread.daemon = True
        self.record_thread.start()
    
    def _record_loop(self):
        """
        音频采集循环
        """
        while self.is_recording:
            try:
                # 读取音频数据
                data = self.input_stream.read(self.chunk, exception_on_overflow=False)
                
                # 计算音量
                audio_np = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_np).mean()
                
                # 调用VAD回调
                if self.vad_callback:
                    self.vad_callback(volume)
                
                # 调用音频回调
                if self.audio_callback:
                    asyncio.run_coroutine_threadsafe(
                        self.audio_callback(data),
                        self.loop
                    )
                    
            except Exception as e:
                print(f"音频采集错误: {e}")
                break
    
    def stop_recording(self):
        """
        停止音频采集
        """
        self.is_recording = False
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        print("🔇 麦克风已关闭")
    
    def play_audio(self, audio_data: bytes, sample_rate: int = 24000):
        """
        播放音频数据
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率
        """
        if not self.output_stream:
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                output=True
            )
        
        try:
            self.is_playing = True
            self.output_stream.write(audio_data)
        except Exception as e:
            print(f"音频播放错误: {e}")
        finally:
            self.is_playing = False
    
    def stop_playing(self):
        """
        停止音频播放
        """
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        self.is_playing = False
    
    def get_volume(self, audio_data: bytes) -> float:
        """
        计算音频音量
        
        Args:
            audio_data: 音频数据
            
        Returns:
            float: 音量值
        """
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return np.abs(audio_np).mean()
    
    def is_speaking(self, audio_data: bytes) -> bool:
        """
        判断是否有语音活动
        
        Args:
            audio_data: 音频数据
            
        Returns:
            bool: 是否有语音活动
        """
        return self.get_volume(audio_data) > self.vad_threshold
    
    def close(self):
        """
        关闭音频管理器
        """
        self.stop_recording()
        self.stop_playing()
        self.audio.terminate()
        print("🎧 音频管理器已关闭")