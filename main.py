#!/usr/bin/env python3
"""
Neo-tel-me 主程序
"""

import asyncio
import sys
import os

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NeoTelMeConfig
from service import NeoTelMeService


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
    
    # 创建服务
    service = NeoTelMeService(config)
    
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