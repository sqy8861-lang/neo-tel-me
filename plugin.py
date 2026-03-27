import asyncio
import threading
from src.core.components.base import BasePlugin
from src.core.components.loader import register_plugin
from src.kernel.logger import get_logger

from config import NeoTelMeConfig
from service import NeoTelMeService
from action import NeoTelMeAction
from websocket_server import WebSocketServer
from http_server import HTTPServer

# 全局服务实例
neo_tel_me_service = None
websocket_server = None
websocket_server_thread = None
http_server = None

logger = get_logger("neo_tel_me")

# 提示词配置
_TARGET_REMINDER_BUCKET = "actor"
_TARGET_REMINDER_NAME = "关于连麦功能的使用"
_CONFERENCE_USAGE_REMINDER = "当用户发送的消息包含#连麦时，必须调用连麦插件neo-tel-me"


def build_neo_tel_me_actor_reminder(plugin) -> str:
    """构建 neo_tel_me 的 actor reminder。"""

    config = getattr(plugin, "config", None)
    if isinstance(config, NeoTelMeConfig) and not config.plugin.inject_system_prompt:
        return ""
    return _CONFERENCE_USAGE_REMINDER


def sync_neo_tel_me_actor_reminder(plugin) -> str:
    """同步 neo_tel_me 的 actor reminder。"""

    from src.core.prompt import get_system_reminder_store

    store = get_system_reminder_store()
    reminder_content = build_neo_tel_me_actor_reminder(plugin)
    if not reminder_content:
        store.delete(_TARGET_REMINDER_BUCKET, _TARGET_REMINDER_NAME)
        logger.debug("neo_tel_me actor reminder 已清理")
        return ""

    store.set(
        _TARGET_REMINDER_BUCKET,
        name=_TARGET_REMINDER_NAME,
        content=reminder_content,
    )
    logger.debug("neo_tel_me actor reminder 已同步")
    return reminder_content


@register_plugin
class NeoTelMePlugin(BasePlugin):
    """Neo-tel-me 插件"""

    plugin_name = "neo_tel_me"
    plugin_version = "1.0.0"
    plugin_author = "MoFox Team"
    plugin_description = "Neo-tel-me — 实时语音对话插件，支持阿里云ASR和MiniMax TTS，实现连麦功能"
    configs = [NeoTelMeConfig]

    async def on_plugin_loaded(self) -> None:
        """插件加载时执行"""
        global neo_tel_me_service, websocket_server, websocket_server_thread, http_server
        # 同步提示词
        sync_neo_tel_me_actor_reminder(self)
        # 初始化服务
        neo_tel_me_service = NeoTelMeService(self.config)
        # 启动 HTTP 服务器（提供H5页面）
        http_server = HTTPServer()
        http_server.start()
        # 启动 WebSocket 服务器（处理实时通信）
        websocket_server = WebSocketServer(self.config)
        # 在单独的线程中运行 WebSocket 服务器
        websocket_server_thread = threading.Thread(
            target=lambda: asyncio.run(websocket_server.start(host="0.0.0.0", port=8766)),
            daemon=True
        )
        websocket_server_thread.start()
        logger.info("Neo-tel-me 插件已加载")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时执行"""
        global neo_tel_me_service, websocket_server, websocket_server_thread, http_server
        # 停止服务
        if neo_tel_me_service and neo_tel_me_service.is_service_running():
            await neo_tel_me_service.stop()
        # 停止 WebSocket 服务器
        if websocket_server:
            await websocket_server.stop()
            websocket_server = None
        if websocket_server_thread:
            websocket_server_thread.join(timeout=5)
            websocket_server_thread = None
        # 停止 HTTP 服务器
        if http_server:
            http_server.stop()
            http_server = None
        # 清理提示词
        from src.core.prompt import get_system_reminder_store
        get_system_reminder_store().delete(_TARGET_REMINDER_BUCKET, _TARGET_REMINDER_NAME)
        logger.info("Neo-tel-me 插件已卸载")

    def get_components(self) -> list[type]:
        """获取插件内所有组件类

        Returns:
            list[type]: 插件内所有组件类的列表
        """
        return [
            NeoTelMeAction
        ]