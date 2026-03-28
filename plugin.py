from src.core.components import BasePlugin, register_plugin
from src.kernel.logger import get_logger

from .config import NeoTelMeConfig
from .service import NeoTelMeService
from .action import NeoTelMeAction

logger = get_logger("neo_tel_me")

# 全局服务实例
neo_tel_me_service = None


@register_plugin
class NeoTelMePlugin(BasePlugin):
    """Neo-tel-me 插件"""

    plugin_name: str = "neo_tel_me"
    plugin_version: str = "1.1.0"
    plugin_author: str = "MoFox Team"
    plugin_description: str = "Neo-tel-me — 实时语音对话插件，支持阿里云ASR和MiniMax TTS，实现连麦功能"
    configs: list[type] = [NeoTelMeConfig]
    dependent_components: list[str] = []

    async def on_plugin_loaded(self) -> None:
        """插件加载时执行"""
        global neo_tel_me_service
        
        # 初始化服务
        neo_tel_me_service = NeoTelMeService(self)
        logger.info("Neo-tel-me 插件已加载")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时执行"""
        global neo_tel_me_service
        if neo_tel_me_service and neo_tel_me_service.is_service_running():
            await neo_tel_me_service.stop()
        logger.info("Neo-tel-me 插件已卸载")

    def get_components(self) -> list[type]:
        """获取插件内所有组件类

        Returns:
            list[type]: 插件内所有组件类的列表
        """
        return [
            NeoTelMeService,
            NeoTelMeAction
        ]