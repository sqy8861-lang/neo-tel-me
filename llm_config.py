from pydantic import BaseModel
from typing import Optional
import toml
import os


class LLMConfig(BaseModel):
    """LLM配置"""

    class Model(BaseModel):
        """模型配置"""

        provider: str = "openai"  # openai, anthropic, etc.
        model_name: str = "gpt-4"
        api_key: str = ""
        base_url: Optional[str] = None
        temperature: float = 0.7
        max_tokens: int = 1000

    class Prompt(BaseModel):
        """提示词配置"""

        personality_prompt: str = ""  # 性格提示词（200字）
        memory_prompt: str = ""  # 记忆提示词（200字）
        max_history: int = 4  # 最近历史记录数量

    class Memory(BaseModel):
        """记忆配置"""

        recent_count: int = 5  # 近期记忆数量
        important_only: bool = True  # 只获取重要记忆

    model: Model = Model()
    prompt: Prompt = Prompt()
    memory: Memory = Memory()

    @classmethod
    def load_from_core_config(cls, config_path: str = "config/core.toml"):
        """
        从核心配置加载LLM配置

        Args:
            config_path: 核心配置文件路径

        Returns:
            LLMConfig: LLM配置实例
        """
        try:
            if not os.path.exists(config_path):
                return cls()

            with open(config_path, "r", encoding="utf-8") as f:
                core_config = toml.load(f)

            # 从核心配置中提取LLM相关配置
            config = cls()

            # 提取模型配置
            if "llm" in core_config:
                llm_config = core_config["llm"]
                config.model.provider = llm_config.get("provider", "openai")
                config.model.model_name = llm_config.get("model_name", "gpt-4")
                config.model.api_key = llm_config.get("api_key", "")
                config.model.base_url = llm_config.get("base_url")
                config.model.temperature = llm_config.get("temperature", 0.7)
                config.model.max_tokens = llm_config.get("max_tokens", 1000)

            return config
        except Exception as e:
            print(f"加载核心配置失败: {e}")
            return cls()
