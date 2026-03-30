"""
连麦消息存储器 - 直接存储连麦消息到数据库和记忆

核心思路：
- 直接调用 StreamManager.add_message() 存入 MoFox.db
- 直接调用 booku_memory 写入记忆
- 不经过 ON_MESSAGE_RECEIVED 事件，避免触发 chatter
- 使用与 QQ 聊天相同的 person_id，确保检索时能关联
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.managers.stream_manager import StreamManager
    from src.core.models.message import Message
    from .llm_config import LLMConfig

logger = get_logger("call_message_storage")


@dataclass
class CallSession:
    """连麦会话信息"""

    stream_id: str
    person_id: str
    user_id: str
    user_nickname: str
    platform: str = "qq"
    chat_type: str = "private"
    start_time: float = field(default_factory=time.time)
    message_count: int = 0


class CallMessageStorage:
    """
    连麦消息存储器

    将连麦消息直接存储到数据库和记忆系统，不经过事件系统。
    关键：使用与 QQ 聊天相同的 person_id，确保检索时能关联。

    使用示例：
        storage = CallMessageStorage(stream_manager, llm_config)
        session = await storage.start_call_session(user_id="12345678", user_nickname="张三")
        await storage.add_user_message("你好")
        await storage.add_bot_message("你好！很高兴见到你。")
        stats = await storage.end_call_session()
    """

    def __init__(
        self, stream_manager: "StreamManager", llm_config: "LLMConfig | None" = None
    ) -> None:
        """
        初始化存储器

        Args:
            stream_manager: StreamManager 实例，用于消息存储
            llm_config: LLM 配置实例，用于记忆判断
        """
        self.stream_manager = stream_manager
        self._llm_config = llm_config
        self._current_session: CallSession | None = None

    async def _store_message_to_history(
        self,
        message: "Message",
        person_id: str,
    ) -> bool:
        """
        直接存储消息到数据库和记忆（不经过事件系统）

        1. 调用 StreamManager.add_message() 存入 MoFox.db
        2. 调用 booku_memory 写入记忆
        3. 不触发 ON_MESSAGE_RECEIVED 事件，避免进入未读列表和触发 chatter

        Args:
            message: 消息对象
            person_id: 发送者的 person_id

        Returns:
            bool: 是否存储成功
        """
        try:
            await self.stream_manager.add_message(message)
            logger.debug(f"连麦消息已直接存入数据库: {message.message_id}")

            asyncio.create_task(self._write_memory_async(message))

            return True
        except Exception as e:
            logger.error(f"存储连麦消息失败: {e}", exc_info=True)
            return False

    async def _write_memory_async(self, message: "Message") -> None:
        """异步写入记忆（后台任务）

        先用 LLM 判断是否值得写入记忆，再调用 booku_memory。
        """
        try:
            content = str(message.content)
            if content.startswith("【连麦消息】"):
                content = content[6:]

            if len(content) < 20:
                return

            should_write = await self._llm_decide_write(content)
            if not should_write:
                logger.debug(f"连麦消息不需要写入记忆: {content[:30]}...")
                return

            from src.app.plugin_system.api.service_api import get_service_class
            from src.core.managers import get_plugin_manager

            service_cls = get_service_class("booku_memory")
            if not service_cls:
                logger.debug("booku_memory service 类不可用，跳过记忆写入")
                return

            plugin_manager = get_plugin_manager()
            plugin = plugin_manager.get_plugin("booku_memory")
            if not plugin:
                logger.debug("booku_memory 插件不可用，跳过记忆写入")
                return

            service = service_cls(plugin=plugin)

            result = await service.upsert_memory(
                content=content,
                bucket="emergent",
                folder_id="events",
                tags=["连麦", "事件"],
                core_tags=["事件"],
                diffusion_tags=["社交", "沟通"],
                opposing_tags=["非正式"],
            )

            if result and result.get("mode"):
                logger.info(
                    f"连麦消息记忆写入成功: {message.message_id}, mode: {result['mode']}"
                )
        except Exception as e:
            logger.error(f"写入连麦消息记忆失败: {e}", exc_info=True)

    async def _llm_decide_write(self, content: str) -> bool:
        """使用 LLM 判断连麦消息是否值得写入记忆

        Args:
            content: 消息内容（已去掉【连麦消息】标记）

        Returns:
            bool: 是否需要写入记忆
        """
        try:
            from src.app.plugin_system.api.llm_api import create_llm_request
            from src.kernel.llm import LLMPayload, ROLE, Text

            prompt = f"""你是一个连麦消息记忆判断助手。
你的任务是判断连麦消息是否值得写入长期记忆。

# 连麦消息内容
{content}

# 判断标准
请根据以下标准判断是否值得写入记忆：
1. **事实信息**：用户姓名、年龄、职业、所在地、联系方式等稳定事实
2. **偏好信息**：喜欢的食物、颜色、品牌、厌恶的事物等
3. **进展信息**：正在进行的项目、目标、待办事项的状态更新
4. **关系信息**：与特定人物的关系变化，如新朋友、冲突、和解等
5. **情感信息**：带有强烈情绪或长期意义的内容

# 输出格式
请返回 JSON 格式：
{{
    "should_write": true/false,
    "reason": "简短的判断理由"
}}

# 注意事项
- 只返回 JSON，不要其他文本
- 如果消息是闲聊、无意义的内容，返回 should_write: false
- 如果消息包含上述任意一种有价值的信息，返回 should_write: true"""

            model_set = self._build_model_set()

            request = create_llm_request(
                request_name="neo_tel_me_memory_writer",
                model_set=model_set,
            )

            request.add_payload(
                LLMPayload(
                    ROLE.SYSTEM,
                    Text("你是一个连麦消息记忆判断助手。只返回 JSON，不要其他文本。"),
                )
            )
            request.add_payload(LLMPayload(ROLE.USER, Text(prompt)))

            response = await request.send(stream=False)
            await response

            response_text = response.message or ""

            import json_repair

            try:
                result = json_repair.loads(response_text)
                if isinstance(result, dict):
                    return bool(result.get("should_write", False))
            except Exception:
                logger.debug(f"LLM 响应解析失败: {response_text[:200]}")

            return False
        except Exception as e:
            logger.error(f"LLM 判断失败: {e}", exc_info=True)
            return False

    def _build_model_set(self):
        """根据配置构建 ModelSet

        Returns:
            list[dict]: ModelSet 格式的模型配置列表
        """
        if not self._llm_config:
            raise ValueError("LLM 配置未设置，无法创建 ModelSet")

        model_config = self._llm_config.model

        return [
            {
                "api_provider": model_config.provider,
                "base_url": model_config.base_url or "",
                "model_identifier": model_config.model_name,
                "api_key": model_config.api_key,
                "client_type": "openai",
                "max_retry": 3,
                "timeout": 30.0,
                "retry_interval": 1.0,
                "price_in": 0.0,
                "price_out": 0.0,
                "temperature": 0.1,
                "max_tokens": 500,
                "max_context": 4000,
                "tool_call_compat": False,
                "extra_params": {},
            }
        ]

    async def start_call_session(
        self,
        user_id: str,
        user_nickname: str,
        person_id: str = "",
    ) -> CallSession:
        """
        开始连麦会话

        Args:
            user_id: 用户 ID（QQ 号）
            user_nickname: 用户昵称
            person_id: 预计算的 person_id（优先使用，确保与 QQ 聊天一致）

        Returns:
            CallSession: 会话信息
        """
        if person_id:
            final_person_id = person_id
        else:
            final_person_id = self._generate_person_id(user_id)

        stream_id = self._generate_stream_id(user_id)

        self._current_session = CallSession(
            stream_id=stream_id,
            person_id=final_person_id,
            user_id=user_id,
            user_nickname=user_nickname,
            start_time=time.time(),
        )

        await self.stream_manager.get_or_create_stream(
            stream_id=stream_id,
            platform="qq",
            user_id=user_id,
            chat_type="private",
        )

        logger.info(
            f"连麦会话已创建: stream_id={stream_id}, "
            f"person_id={final_person_id}, user={user_nickname}"
        )

        return self._current_session

    async def add_user_message(self, content: str) -> "Message":
        """
        添加用户消息

        Args:
            content: 消息内容

        Returns:
            Message: 创建的消息对象

        Raises:
            RuntimeError: 未启动连麦会话时抛出
        """
        if not self._current_session:
            raise RuntimeError("未启动连麦会话，请先调用 start_call_session")

        self._current_session.message_count += 1
        message_id = self._generate_message_id()

        message = await self._build_message(
            message_id=message_id,
            content=content,
            is_user=True,
        )

        await self._store_message_to_history(message, self._current_session.person_id)

        logger.debug(f"连麦用户消息已存储: {content[:50]}...")

        return message

    async def add_bot_message(self, content: str) -> "Message":
        """
        添加 Bot 回复消息

        Args:
            content: 回复内容

        Returns:
            Message: 创建的消息对象

        Raises:
            RuntimeError: 未启动连麦会话时抛出
        """
        if not self._current_session:
            raise RuntimeError("未启动连麦会话，请先调用 start_call_session")

        self._current_session.message_count += 1
        message_id = self._generate_message_id()

        message = await self._build_message(
            message_id=message_id,
            content=content,
            is_user=False,
        )

        await self._store_message_to_history(message, "bot")

        logger.debug(f"连麦 Bot 回复已存储: {content[:50]}...")

        return message

    async def end_call_session(self) -> dict:
        """
        结束连麦会话

        Returns:
            dict: 会话统计信息，包含 stream_id、person_id、消息数、时长等
        """
        if not self._current_session:
            return {}

        session = self._current_session
        duration = time.time() - session.start_time

        stats = {
            "stream_id": session.stream_id,
            "person_id": session.person_id,
            "user_id": session.user_id,
            "user_nickname": session.user_nickname,
            "message_count": session.message_count,
            "duration_seconds": round(duration, 2),
            "start_time": session.start_time,
            "end_time": time.time(),
        }

        logger.info(
            f"连麦会话已结束: {session.user_nickname}, "
            f"消息数={session.message_count}, 时长={duration:.1f}s"
        )

        self._current_session = None

        return stats

    def _generate_person_id(self, user_id: str) -> str:
        """
        生成统一的 person_id

        格式与 QQ 聊天一致：qq_{user_id}
        这确保了连麦记录和 QQ 聊天记录能被一起检索到。

        Args:
            user_id: 用户 ID（QQ 号）

        Returns:
            str: person_id
        """
        if user_id and user_id.strip():
            return f"qq_{user_id}"
        else:
            return f"qq_call_{int(time.time())}"

    def _generate_stream_id(self, user_id: str) -> str:
        """
        生成连麦流 ID

        使用与 QQ 私聊相同的 stream_id 格式（SHA-256 哈希），
        确保连麦消息能被正确检索到。

        Args:
            user_id: 用户 ID（QQ 号）

        Returns:
            str: stream_id（与 QQ 私聊相同）
        """
        from src.core.models.stream import ChatStream

        return ChatStream.generate_stream_id(platform="qq", user_id=user_id)

    def _generate_message_id(self) -> str:
        """
        生成消息 ID

        格式：call_msg_{timestamp}_{sequence}

        Returns:
            str: message_id
        """
        timestamp = int(time.time() * 1000)
        seq = self._current_session.message_count if self._current_session else 0
        return f"call_msg_{timestamp}_{seq:03d}"

    async def _build_message(
        self,
        message_id: str,
        content: str,
        is_user: bool,
    ) -> "Message":
        """
        构建 Message 对象

        关键：person_id 必须与 QQ 聊天一致，通过 extra 传递

        Args:
            message_id: 消息 ID
            content: 消息内容
            is_user: 是否为用户消息

        Returns:
            Message: 消息对象
        """
        from src.core.models.message import Message, MessageType

        session = self._current_session

        if is_user:
            sender_id = session.user_id
            sender_name = session.user_nickname
            person_id = session.person_id
        else:
            sender_id = "bot"
            sender_name = "Bot"
            person_id = "bot"

        return Message(
            message_id=message_id,
            stream_id=session.stream_id,
            platform="qq",
            chat_type="private",
            time=time.time(),
            message_type=MessageType.TEXT,
            content=f"【连麦消息】{content}",
            processed_plain_text=f"【连麦消息】{content}",
            sender_id=sender_id,
            sender_name=sender_name,
            person_id=person_id,
        )

    @property
    def current_session(self) -> CallSession | None:
        """获取当前会话"""
        return self._current_session

    @property
    def is_active(self) -> bool:
        """检查是否有活跃会话"""
        return self._current_session is not None

    @property
    def stream_id(self) -> str | None:
        """获取当前 stream_id"""
        return self._current_session.stream_id if self._current_session else None

    @property
    def person_id(self) -> str | None:
        """获取当前 person_id"""
        return self._current_session.person_id if self._current_session else None
