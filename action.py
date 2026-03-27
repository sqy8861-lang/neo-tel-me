from src.core.components.base.action import BaseAction


class NeoTelMeAction(BaseAction):
    """Neo-tel-me Action：启动/停止实时语音对话"""

    action_name = "neo_tel_me"
    action_description = "启动或停止Neo-tel-me实时语音对话服务。当服务启动时，系统会监听麦克风输入，将语音转换为文本，生成回复后再转换为语音播放。"

    chatter_allow: list[str] = []

    async def execute(self, action: str = "start") -> tuple[bool, str]:
        """执行Neo-tel-me动作

        Args:
            action: 动作类型，可选值：start（启动）、stop（停止）
        """
        from .plugin import neo_tel_me_service
        
        if action == "start":
            if neo_tel_me_service.is_service_running():
                return True, "Neo-tel-me 服务已经在运行中"
            
            success = await neo_tel_me_service.start()
            if success:
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