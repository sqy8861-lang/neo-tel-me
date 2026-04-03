"""Neo-tel-me 命令组件

提供连麦功能的命令式触发接口。
"""
from src.app.plugin_system.base import BaseCommand, cmd_route
from src.core.components.types import PermissionLevel
from src.kernel.logger import get_logger

logger = get_logger("neo_tel_me")


class NeoTelMeCommand(BaseCommand):
    """连麦命令

    使用 # 作为命令前缀，支持启动和停止连麦服务。

    Examples:
        #连麦 - 启动连麦
        #连麦 stop - 停止连麦
    """

    command_name = "连麦"
    command_description = "启动或停止实时语音连麦服务"
    command_prefix = "#"
    permission_level = PermissionLevel.USER

    dependencies: list[str] = []

    async def execute(self, message_text: str) -> tuple[bool, str]:
        """执行命令的入口方法

        重写此方法以支持默认启动连麦。

        Args:
            message_text: 已完成归一化的子路由文本

        Returns:
            tuple[bool, str]: (是否成功, 返回结果/错误信息)
        """
        message_text = message_text.strip()

        if not message_text:
            return await self.handle_start()

        return await self._route_and_execute(message_text)

    async def handle_start(self) -> tuple[bool, str]:
        """启动连麦

        Returns:
            tuple[bool, str]: (是否成功, 响应消息)
        """
        from .plugin import neo_tel_me_service

        if neo_tel_me_service.is_service_running():
            return True, "连麦服务已在运行中"

        user_id = ""
        user_nickname = ""
        person_id = ""

        try:
            from src.core.utils.user_query_helper import get_user_query_helper
            from src.core.components.types import StreamContext

            if hasattr(self, "stream_id") and self.stream_id:
                stream_context = StreamContext.from_stream_id(self.stream_id)
                if stream_context:
                    user_id = stream_context.user_id or ""
                    user_nickname = stream_context.user_nickname or ""
                    platform = stream_context.platform or "qq"
                    if user_id:
                        person_id = get_user_query_helper().generate_person_id(
                            platform, user_id
                        )
        except Exception as e:
            logger.warning(f"获取用户信息失败: {e}")

        logger.info(
            f"连麦命令触发: user_id={user_id}, nickname={user_nickname}, person_id={person_id}"
        )

        success = await neo_tel_me_service.start(
            user_id=user_id,
            user_nickname=user_nickname,
            person_id=person_id,
        )

        if success:
            try:
                cfg = neo_tel_me_service._cfg()
                if hasattr(cfg, "websocket") and cfg.websocket.enabled:
                    host = (
                        getattr(cfg.websocket, "public_ip", "")
                        or cfg.websocket.host
                    )
                    port = cfg.websocket.port
                    use_ssl = getattr(cfg.websocket, "use_ssl", False)
                    protocol = "https" if use_ssl else "http"
                    web_url = f"{protocol}://{host}:{port}"
                    return True, f"连麦已启动，请访问：{web_url}"
            except Exception as e:
                logger.error(f"获取配置失败: {e}")

            return True, "连麦服务已成功启动"
        else:
            return False, "连麦服务启动失败"

    @cmd_route("stop")
    async def handle_stop(self) -> tuple[bool, str]:
        """停止连麦

        Returns:
            tuple[bool, str]: (是否成功, 响应消息)
        """
        from .plugin import neo_tel_me_service

        if not neo_tel_me_service.is_service_running():
            return True, "连麦服务已停止"

        await neo_tel_me_service.stop()
        return True, "连麦服务已成功停止"
