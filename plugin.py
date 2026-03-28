from src.core.components import BasePlugin, register_plugin
from src.kernel.logger import get_logger
import os
import subprocess

from .config import NeoTelMeConfig
from .service import NeoTelMeService
from .action import NeoTelMeAction

logger = get_logger("neo_tel_me")

# 全局服务实例
neo_tel_me_service = None


def check_and_download_aliyun_sdk():
    """检查并下载阿里云SDK"""
    sdk_dir = os.path.join(os.path.dirname(__file__), "alibabacloud-nls-python-sdk")
    if not os.path.exists(sdk_dir):
        logger.info("阿里云SDK目录不存在，开始下载...")
        try:
            # 使用git clone下载SDK
            subprocess.run(
                ["git", "clone", "https://github.com/aliyun/alibabacloud-nls-python-sdk.git", sdk_dir],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("阿里云SDK下载成功")
        except Exception as e:
            logger.error(f"阿里云SDK下载失败: {e}")
            return False
    else:
        logger.info("阿里云SDK目录已存在")
    return True


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
        
        # 检查并下载阿里云SDK
        if not check_and_download_aliyun_sdk():
            logger.error("阿里云SDK下载失败，插件加载失败")
            return
        
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