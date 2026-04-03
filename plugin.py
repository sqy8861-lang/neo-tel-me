from src.app.plugin_system.base import BasePlugin, register_plugin
from src.kernel.logger import get_logger
import json
from pathlib import Path

from .config import NeoTelMeConfig
from .service import NeoTelMeService
from .action import NeoTelMeAction
from .llm_config import LLMConfig
from .llm_client import LLMClient
from .prompt_refiner import PromptRefiner

logger = get_logger("neo_tel_me")

# 全局服务实例
neo_tel_me_service = None
# 全局系统提示词
system_prompt = ""

# 提示词存储路径

# 计算主项目根目录（向上两级）
PROJECT_ROOT = Path(__file__).parent.parent.parent
# 在data目录下创建专门的插件文件夹
DATA_DIR = PROJECT_ROOT / "data" / "neo_tel_me"
SYSTEM_PROMPT_FILE = DATA_DIR / "system_prompt.json"


@register_plugin
class NeoTelMePlugin(BasePlugin):
    """Neo-tel-me 插件"""

    plugin_name: str = "neo_tel_me"
    plugin_version: str = "1.1.0"
    plugin_author: str = "MoFox Team"
    plugin_description: str = (
        "Neo-tel-me — 实时语音对话插件，支持阿里云ASR和MiniMax TTS，实现连麦功能"
    )
    configs: list[type] = [NeoTelMeConfig]
    dependent_components: list[str] = []

    async def on_plugin_loaded(self) -> None:
        """插件加载时执行"""
        global neo_tel_me_service, system_prompt

        # 确保数据目录存在
        DATA_DIR.mkdir(exist_ok=True)

        # 加载或生成系统提示词
        system_prompt = await self._load_or_generate_system_prompt()

        # 初始化服务
        neo_tel_me_service = NeoTelMeService(self, system_prompt)

        logger.info("Neo-tel-me 插件已加载")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时执行"""
        global neo_tel_me_service
        if neo_tel_me_service and neo_tel_me_service.is_service_running():
            await neo_tel_me_service.stop()
        logger.info("Neo-tel-me 插件已卸载")

    async def _load_or_generate_system_prompt(self) -> str:
        """
        加载或生成系统提示词

        Returns:
            str: 系统提示词
        """
        # 尝试加载已存储的系统提示词
        if SYSTEM_PROMPT_FILE.exists():
            try:
                with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prompt = data.get("system_prompt", "")
                    if prompt:
                        logger.info("成功加载已存储的系统提示词")
                        return prompt
            except Exception as e:
                logger.error(f"加载系统提示词失败: {e}")

        # 生成新的系统提示词
        logger.info("未找到存储的系统提示词，正在生成新的")

        # 加载配置
        cfg = self.config
        if not isinstance(cfg, NeoTelMeConfig):
            raise RuntimeError("neo_tel_me plugin config 未正确加载")

        # 初始化LLM配置
        llm_config = LLMConfig()
        llm_config.model.provider = cfg.llm.model.provider
        llm_config.model.model_name = cfg.llm.model.model_name
        llm_config.model.api_key = cfg.llm.model.api_key
        llm_config.model.base_url = cfg.llm.model.base_url
        llm_config.model.temperature = cfg.llm.model.temperature
        llm_config.model.max_tokens = cfg.llm.model.max_tokens

        # 初始化LLM客户端
        llm_client = LLMClient(llm_config)
        await llm_client.initialize()

        # 初始化提示词精炼器
        prompt_refiner = PromptRefiner()
        prompt = await prompt_refiner.initialize(llm_client)

        # 存储系统提示词
        try:
            with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
                json.dump({"system_prompt": prompt}, f, ensure_ascii=False, indent=2)
            logger.info("系统提示词已存储")
        except Exception as e:
            logger.error(f"存储系统提示词失败: {e}")

        # 关闭LLM客户端
        await llm_client.close()

        return prompt

    def get_components(self) -> list[type]:
        """获取插件内所有组件类

        Returns:
            list[type]: 插件内所有组件类的列表
        """
        return [
            NeoTelMeService,
            NeoTelMeAction,
        ]
