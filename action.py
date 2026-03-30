from src.app.plugin_system.base import BaseAction
from src.kernel.logger import get_logger

logger = get_logger("neo_tel_me")


class NeoTelMeAction(BaseAction):
    """Neo-tel-me Action：启动/停止实时语音对话"""

    action_name = "neo_tel_me"
    action_description = "启动或停止Neo-tel-me实时语音对话服务。当服务启动时，系统会监听麦克风输入，将语音转换为文本，生成回复后再转换为语音播放。"

    chatter_allow: list[str] = []

    async def execute(self, action: str = "start", user_nickname: str = "") -> tuple[bool, str]:
        """执行Neo-tel-me动作

        Args:
            action: 动作类型，可选值：start（启动）、stop（停止）
            user_nickname: 用户昵称，用于连麦时标识用户（可选，会自动从消息上下文获取）
        """
        from .plugin import neo_tel_me_service
        
        if action == "start":
            if neo_tel_me_service.is_service_running():
                return True, "Neo-tel-me 服务已经在运行中"
            
            user_id = ""
            actual_nickname = user_nickname
            person_id = ""
            
            if hasattr(self, 'message') and self.message:
                from_user = getattr(self.message, 'from_user', None)
                if from_user:
                    user_id = getattr(from_user, 'user_id', '')
                    if not actual_nickname:
                        actual_nickname = getattr(from_user, 'nickname', '')
            
            if not user_id and hasattr(self, 'chat_stream') and self.chat_stream:
                context = getattr(self.chat_stream, 'context', None)
                if context:
                    user_id = getattr(context, 'triggering_user_id', '') or ''
            
            if user_id and self.chat_stream:
                from src.core.utils.user_query_helper import get_user_query_helper
                platform = getattr(self.chat_stream, 'platform', 'qq')
                person_id = get_user_query_helper().generate_person_id(platform, user_id)
            
            logger.info(f"连麦触发: user_id={user_id}, nickname={actual_nickname}, person_id={person_id}")
            
            success = await neo_tel_me_service.start(
                user_id=user_id,
                user_nickname=actual_nickname,
                person_id=person_id,
            )
            if success:
                # 检查是否启用了 WebSocket 模式
                try:
                    cfg = neo_tel_me_service._cfg()
                    if hasattr(cfg, 'websocket') and cfg.websocket.enabled:
                        # 优先使用 public_ip，如果未配置则使用 host
                        host = getattr(cfg.websocket, 'public_ip', '') or cfg.websocket.host
                        port = cfg.websocket.port
                        # 根据 SSL 配置选择协议
                        use_ssl = getattr(cfg.websocket, 'use_ssl', False)
                        protocol = "https" if use_ssl else "http"
                        # 构建网页链接
                        web_url = f"{protocol}://{host}:{port}"
                        # 直接发送网页链接给用户
                        await self._send_to_stream(f"连麦功能已经启动啦，链接在这里：{web_url}")
                        return True, f"连麦功能已经启动啦，链接在这里：{web_url}"
                except Exception as e:
                    # 如果获取配置失败，返回普通成功消息
                    logger.error(f"获取配置失败: {e}")
                
                return True, "Neo-tel-me 服务已成功启动"
            else:
                return False, "Neo-tel-me 服务启动失败"
        
        elif action == "stop":
            if not neo_tel_me_service.is_service_running():
                return True, "Neo-tel-me 服务已经停止"
            
            await neo_tel_me_service.stop()
            return True, "Neo-tel-me 服务已成功停止"
        
        else:
            return False, f"未知的动作类型: {action}"