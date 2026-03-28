import toml
import os

class NeoTelMeConfig:
    """Neo-tel-me 配置"""
    
    def __init__(self, config_file="config.toml"):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = toml.load(f)
            
            # 插件基础配置
            self.plugin