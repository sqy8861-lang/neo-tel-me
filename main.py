#!/usr/bin/env python3
"""
Neo-tel-me 主程序
"""

import asyncio
import sys
import os
import json
from pathlib import Path

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NeoTelMeConfig
from service import NeoTelMeService
from llm_config import LLMConfig
from llm_client import LLMClient
from prompt_refiner import PromptRefiner

# 提示词存储路径
DATA_DIR = Path("data")
SYSTEM_PROMPT_FILE = DATA_DIR / "system_prompt.json"


async def load_or_generate_system_prompt(config) -> str:
    """
    加载或生成系统提示词
    
    Args:
        config: 配置对象
        
    Returns:
        str: 系统提示词
    """
    # 确保数据目录存在
    DATA_DIR.mkdir(exist_ok=True)
    
    # 尝试加载已存储的系统提示词
    if SYSTEM_PROMPT_FILE.exists():
        try:
            with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                prompt = data.get('system_prompt', '')
                if prompt:
                    print("成功加载已存储的系统提示词")
                    return prompt
        except Exception as e:
            print(f"加载系统提示词失败: {e}")
    
    # 生成新的系统提示词
    print("未找到存储的系统提示词，正在生成新的")
    
    # 初始化LLM配置
    llm_config = LLMConfig()
    llm_config.model.provider = config.llm.model.provider
    llm_config.model.model_name = config.llm.model.model_name
    llm_config.model.api_key = config.llm.model.api_key
    llm_config.model.base_url = config.llm.model.base_url
    llm_config.model.temperature = config.llm.model.temperature
    llm_config.model.max_tokens = config.llm.model.max_tokens
    
    # 初始化LLM客户端
    llm_client = LLMClient(llm_config)
    await llm_client.initialize()
    
    # 初始化提示词精炼器
    prompt_refiner = PromptRefiner()
    prompt = await prompt_refiner.initialize(llm_client)
    
    # 存储系统提示词
    try:
        with open(SYSTEM_PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump({'system_prompt': prompt}, f, ensure_ascii=False, indent=2)
        print("系统提示词已存储")
    except Exception as e:
        print(f"存储系统提示词失败: {e}")
    
    # 关闭LLM客户端
    await llm_client.close()
    
    return prompt


async def main():
    """主函数"""
    print("🎙️ Neo-tel-me - 实时语音对话AI助手")
    print("=" * 50)
    
    # 检查配置文件
    config_file = "config.toml"
    if not os.path.exists(config_file):
        print(f"❌ 配置文件 {config_file} 不存在！")
        print(f"💡 请复制 config.example.toml 为 config.toml 并填写你的API密钥")
        sys.exit(1)
    
    # 加载配置
    try:
        # 注意：这里需要根据实际的配置加载方式进行调整
        # 暂时使用默认配置
        config = NeoTelMeConfig()
        print("✅ 配置文件加载成功")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        sys.exit(1)
    
    # 加载或生成系统提示词
    system_prompt = await load_or_generate_system_prompt(config)
    
    # 创建服务
    service = NeoTelMeService(config, system_prompt)
    
    # 启动服务
    print("\n🚀 正在启动服务...")
    if await service.start():
        print("\n💡 使用说明：")
        print("  - 说话即可开始对话")
        print("  - 大声说话可打断AI")
        print("  - 按 Ctrl+C 停止服务")
        print("\n" + "=" * 50)
        
        try:
            # 保持运行
            while service.is_service_running():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 正在停止服务...")
    else:
        print("❌ 服务启动失败")
        sys.exit(1)
    
    # 停止服务
    await service.stop()
    print("✅ 服务已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
        sys.exit(0)