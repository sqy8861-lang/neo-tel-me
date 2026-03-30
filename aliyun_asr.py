import asyncio
import time
from typing import Optional, Callable

import nls


class AliyunRealtimeASR:
    """
    阿里云实时语音识别客户端（使用SDK）
    """

    def __init__(
        self,
        appkey: str,
        access_key_id: str,
        access_key_secret: str,
        sample_rate: int = 16000,
        format: str = "pcm",
    ):
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
        self.asr = None
        self.on_result: Optional[Callable] = None
        self.connected = False
        self.is_ready = False
        self.recognized_text = ""
        self.token = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.last_callback_text = ""
        self.last_callback_time = 0

    def _on_sentence_begin(self, message, *args):
        """一句话开始回调"""
        print("一句话开始")

    def _on_sentence_end(self, message, *args):
        """一句话结束回调"""
        import json

        try:
            result = json.loads(message)
            text = result.get("payload", {}).get("result", "")
            print(f"[OK] [一句话结束] {text}")
            if text:
                self.recognized_text = text
                if self.on_result:
                    print(f"[ASR] 准备触发回调，文本: {text}")
                    self._schedule_callback(text)
                else:
                    print("[WARN] [ASR] on_result 回调未设置！")
        except Exception as e:
            print(f"解析一句话结束结果失败: {e}")
        print("一句话结束")

    def _on_start(self, message, *args):
        """实时识别就绪回调"""
        print("[OK] 阿里云 ASR 准备就绪，可以发送音频")
        self.is_ready = True

    def _on_error(self, message, *args):
        """错误回调"""
        print(f"[FAIL] 阿里云 ASR 错误: {message}")
        self.connected = False

    def _on_close(self, *args):
        """连接关闭回调"""
        print("[CLOSE] 阿里云 ASR 连接已关闭")
        self.connected = False
        self.is_ready = False

    def _schedule_callback(self, text: str):
        """
        在正确的事件循环中调度回调函数

        Args:
            text: 识别文本
        """
        if not text or not text.strip():
            return

        current_time = time.time()
        if (
            text == self.last_callback_text
            and (current_time - self.last_callback_time) < 2
        ):
            print(f"[ASR] 跳过重复回调: {text}")
            return

        self.last_callback_text = text
        self.last_callback_time = current_time

        if self.event_loop and self.on_result:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.on_result(text), self.event_loop
                )
                print(f"[ASR] 回调已调度到事件循环: {text}")
            except Exception as e:
                print(f"[ASR] 调度回调失败: {e}")
        else:
            print(
                f"[ASR] 无法调度: event_loop={self.event_loop is not None}, on_result={self.on_result is not None}"
            )

    def _on_result_changed(self, message, *args):
        """中间结果回调"""
        import json

        try:
            result = json.loads(message)
            text = result.get("payload", {}).get("result", "")
            print(f"[识别中] {text}")
        except Exception as e:
            print(f"解析中间结果失败: {e}")

    def _on_completed(self, message, *args):
        """识别会话结束回调（整个识别过程结束，不触发回调）"""
        print("[OK] [识别会话结束]")

    def generate_token(self) -> str:
        """
        生成阿里云token

        Returns:
            str: 生成的token
        """
        from nls.token import getToken

        try:
            token = getToken(self.access_key_id, self.access_key_secret)
            print(f"使用SDK获取的token: {token}")
            return token
        except Exception as e:
            print(f"获取token失败: {e}")
            # 手动生成token作为备用
            import time
            import base64
            import hmac
            import hashlib

            # 生成时间戳
            timestamp = str(int(time.time()))
            # 生成签名
            signature_str = f"{self.access_key_id}\n{timestamp}"
            signature = hmac.new(
                self.access_key_secret.encode("utf-8"),
                signature_str.encode("utf-8"),
                hashlib.sha1,
            ).digest()
            signature_base64 = base64.b64encode(signature).decode("utf-8")
            # 构建token
            token = f"{self.access_key_id}:{signature_base64}:{timestamp}"
            print(f"手动生成的token: {token}")
            return token

    async def connect(self, on_result_callback: Callable) -> bool:
        """
        连接阿里云 ASR

        Args:
            on_result_callback: 识别结果回调函数

        Returns:
            bool: 连接是否成功
        """
        self.on_result = on_result_callback
        self.event_loop = asyncio.get_running_loop()

        try:
            self.token = self.generate_token()
            print(f"生成的token: {self.token}")

            self.asr = nls.NlsSpeechTranscriber(
                url="wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1",
                token=self.token,
                appkey=self.appkey,
                on_sentence_begin=self._on_sentence_begin,
                on_sentence_end=self._on_sentence_end,
                on_start=self._on_start,
                on_result_changed=self._on_result_changed,
                on_completed=self._on_completed,
                on_error=self._on_error,
                on_close=self._on_close,
                callback_args=[self],
            )

            print("正在连接阿里云ASR服务...")
            try:
                self.asr.start(
                    aformat=self.format,
                    sample_rate=self.sample_rate,
                    enable_intermediate_result=True,
                    enable_punctuation_prediction=True,
                    enable_inverse_text_normalization=True,
                )

                # 等待准备就绪
                print("等待ASR服务准备就绪...")
                for _ in range(20):  # 增加等待时间
                    if self.is_ready:
                        print("✅ 阿里云 ASR 已连接并准备就绪")
                        self.connected = True
                        return True
                    await asyncio.sleep(0.5)
                print("❌ 阿里云 ASR 准备超时")
                return False
            except Exception as e:
                print(f"❌ 阿里云 ASR 启动失败: {e}")
                return False

        except Exception as e:
            print(f"❌ 阿里云 ASR 连接失败: {e}")
            return False

    async def send_audio(self, audio_bytes: bytes) -> bool:
        """
        发送音频数据到 ASR

        Args:
            audio_bytes: 音频数据

        Returns:
            bool: 发送是否成功
        """
        if not self.connected or not self.asr or not self.is_ready:
            return False

        try:
            # 发送音频数据
            success = self.asr.send_audio(audio_bytes)
            return success
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False

    async def stop_transcription(self):
        """
        停止识别
        """
        if self.asr:
            try:
                success = self.asr.stop()
                print(f"📢 已停止识别: {success}")
            except Exception as e:
                print(f"停止识别失败: {e}")

    async def close(self):
        """
        关闭连接
        """
        if self.asr:
            try:
                # 停止识别
                await self.stop_transcription()
                # 等待一段时间让服务端处理
                await asyncio.sleep(0.5)
                # 关闭连接
                self.asr.shutdown()
                print("🔌 阿里云 ASR 连接已关闭")
            except Exception as e:
                print(f"关闭连接失败: {e}")
        # 无论是否成功关闭，都重置状态
        self.connected = False
        self.is_ready = False
        self.asr = None
        self.token = None
