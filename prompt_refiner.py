import toml
import os
from typing import List, Dict, Optional


class PromptRefiner:
    """提示词精炼器"""
    
    def __init__(self, custom_prompt_path: str = "config/plugins/custom_prompt_injector/config.toml"):
        """
        初始化提示词精炼器
        
        Args:
            custom_prompt_path: custom_prompt_injector配置文件路径
        """
        self.custom_prompt_path = custom_prompt_path
        self.personality_prompt = ""
        self.prompts_data = []
    
    def load_custom_prompts(self) -> List[Dict]:
        """
        加载custom_prompt_injector配置中的prompts
        
        Returns:
            List[Dict]: prompts列表
        """
        if not os.path.exists(self.custom_prompt_path):
            print(f"custom_prompt_injector配置文件不存在: {self.custom_prompt_path}")
            return []
        
        try:
            with open(self.custom_prompt_path, 'r', encoding='utf-8') as f:
                config = toml.load(f)
            
            prompts = config.get('prompts', [])
            self.prompts_data = prompts
            return prompts
        except Exception as e:
            print(f"加载custom_prompt_injector配置失败: {e}")
            return []
    
    def filter_afc_prompts(self, prompts: List[Dict]) -> List[Dict]:
        """
        筛选出enable_afc = false的prompts
        
        Args:
            prompts: prompts列表
            
        Returns:
            List[Dict]: 筛选后的prompts
        """
        filtered = [p for p in prompts if p.get('enable_afc', False) == False]
        print(f"筛选出 {len(filtered)} 个非AFC模式的prompts")
        return filtered
    
    def extract_content(self, prompts: List[Dict]) -> str:
        """
        提取prompts的content内容
        
        Args:
            prompts: prompts列表
            
        Returns:
            str: 合并的content内容
        """
        contents = []
        for prompt in prompts:
            content = prompt.get('content', '')
            if content:
                contents.append(content)
        
        return '\n\n'.join(contents)
    
    async def refine_personality_prompt(self, llm_client, raw_content: str) -> str:
        """
        使用LLM精炼性格提示词为200字左右
        
        Args:
            llm_client: LLM客户端
            raw_content: 原始提示词内容
            
        Returns:
            str: 精炼后的性格提示词
        """
        if not llm_client:
            print("LLM客户端未初始化，使用原始内容")
            return raw_content[:200]
        
        try:
            prompt = f"""请将以下机器人性格和表达习惯的描述精炼为200字左右的提示词，保留核心性格特征和表达方式：

{raw_content}

要求：
1. 保持在200字左右
2. 保留核心性格特征
3. 保留关键表达习惯
4. 语言简洁有力
5. 适合作为LLM的系统提示词"""

            response = await llm_client.generate(prompt, max_tokens=300)
            
            if response:
                self.personality_prompt = response[:200]
                print(f"✅ 性格提示词精炼完成: {len(self.personality_prompt)}字")
                return self.personality_prompt
            else:
                print("LLM返回空内容，使用原始内容")
                return raw_content[:200]
        except Exception as e:
            print(f"精炼性格提示词失败: {e}")
            return raw_content[:200]
    
    async def initialize(self, llm_client=None) -> str:
        """
        初始化提示词精炼器
        
        Args:
            llm_client: LLM客户端（可选）
            
        Returns:
            str: 精炼后的性格提示词
        """
        # 加载custom prompts
        prompts = self.load_custom_prompts()
        
        if not prompts:
            print("没有找到custom prompts，使用默认性格提示词")
            return "你是辞安，用户的傲娇系温柔守护者。"
        
        # 筛选非AFC模式的prompts
        afc_prompts = self.filter_afc_prompts(prompts)
        
        if not afc_prompts:
            print("没有找到非AFC模式的prompts，使用默认性格提示词")
            return "你是辞安，用户的傲娇系温柔守护者。"
        
        # 提取内容
        raw_content = self.extract_content(afc_prompts)
        print(f"提取到 {len(raw_content)} 字的原始内容")
        
        # 精炼提示词
        refined_prompt = await self.refine_personality_prompt(llm_client, raw_content)
        
        return refined_prompt
    
    def get_personality_prompt(self) -> str:
        """
        获取精炼后的性格提示词
        
        Returns:
            str: 性格提示词
        """
        return self.personality_prompt
    
    def set_personality_prompt(self, prompt: str):
        """
        设置性格提示词
        
        Args:
            prompt: 性格提示词
        """
        self.personality_prompt = prompt[:200]
        print(f"设置性格提示词: {len(self.personality_prompt)}字")