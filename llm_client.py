import aiohttp
import json
from typing import Optional, List
from .llm_config import LLMConfig


class LLMClient:
    """LLM客户端"""
    
    def __init__(self, config: LLMConfig):
        """
        初始化LLM客户端
        
        Args:
            config: LLM配置
        """
        self.config = config
        self.session = None
        self.system_prompt = ""
        self.memory_prompt = ""
    
    async def initialize(self):
        """初始化客户端"""
        self.session = aiohttp.ClientSession()
        print("LLM客户端初始化完成")
    
    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
            print("LLM客户端已关闭")
    
    def set_system_prompt(self, prompt: str):
        """
        设置系统提示词（性格提示词）
        
        Args:
            prompt: 系统提示词
        """
        self.system_prompt = prompt
        print(f"设置系统提示词: {len(prompt)}字")
    
    def set_memory_prompt(self, prompt: str):
        """
        设置记忆提示词
        
        Args:
            prompt: 记忆提示词
        """
        self.memory_prompt = prompt
        print(f"设置记忆提示词: {len(prompt)}字")
    
    def build_full_prompt(self, user_input: str, history: str) -> str:
        """
        构建完整的提示词
        
        Args:
            user_input: 用户输入
            history: 历史记录
            
        Returns:
            str: 完整的提示词
        """
        # 构建系统提示词
        system_parts = []
        
        if self.system_prompt:
            system_parts.append(f"【性格特征】\n{self.system_prompt}")
        
        if self.memory_prompt:
            system_parts.append(f"【记忆背景】\n{self.memory_prompt}")
        
        system_text = '\n\n'.join(system_parts) if system_parts else ""
        
        # 构建完整提示词
        full_prompt = f"""{system_text}

【对话历史】
{history}

【当前输入】
用户: {user_input}

【回复要求】
1. 根据性格特征和记忆背景生成回复
2. 保持与历史对话的连贯性
3. 回复要自然、符合人设
4. 回复要简洁，适合语音对话
5. 不要重复历史对话中的内容

请生成回复:"""
        
        return full_prompt
    
    async def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """
        生成回复
        
        Args:
            prompt: 提示词
            max_tokens: 最大token数
            
        Returns:
            str: 生成的回复
        """
        if not self.session:
            await self.initialize()
        
        max_tokens = max_tokens or self.config.model.max_tokens
        
        try:
            if self.config.model.provider == "openai":
                return await self._generate_openai(prompt, max_tokens)
            elif self.config.model.provider == "anthropic":
                return await self._generate_anthropic(prompt, max_tokens)
            else:
                print(f"不支持的LLM提供商: {self.config.model.provider}")
                return ""
        except Exception as e:
            print(f"LLM生成失败: {e}")
            return ""
    
    async def _generate_openai(self, prompt: str, max_tokens: int) -> str:
        """
        使用OpenAI API生成回复
        
        Args:
            prompt: 提示词
            max_tokens: 最大token数
            
        Returns:
            str: 生成的回复
        """
        url = self.config.model.base_url or "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.config.model.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model.model_name,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "请直接生成回复，不要包含任何解释或格式标记。"}
            ],
            "temperature": self.config.model.temperature,
            "max_tokens": max_tokens
        }
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"OpenAI API错误: {response.status} - {error_text}")
                return ""
            
            result = await response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                print("OpenAI API返回空结果")
                return ""
    
    async def _generate_anthropic(self, prompt: str, max_tokens: int) -> str:
        """
        使用Anthropic API生成回复
        
        Args:
            prompt: 提示词
            max_tokens: 最大token数
            
        Returns:
            str: 生成的回复
        """
        url = self.config.model.base_url or "https://api.anthropic.com/v1/messages"
        
        headers = {
            "x-api-key": self.config.model.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.config.model.model_name,
            "max_tokens": max_tokens,
            "system": prompt,
            "messages": [
                {"role": "user", "content": "请直接生成回复，不要包含任何解释或格式标记。"}
            ],
            "temperature": self.config.model.temperature
        }
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"Anthropic API错误: {response.status} - {error_text}")
                return ""
            
            result = await response.json()
            
            if "content" in result and len(result["content"]) > 0:
                return result["content"][0]["text"].strip()
            else:
                print("Anthropic API返回空结果")
                return ""
    
    async def generate_response(self, user_input: str, history: str) -> str:
        """
        生成对话回复（完整流程）
        
        Args:
            user_input: 用户输入
            history: 历史记录
            
        Returns:
            str: 生成的回复
        """
        # 构建完整提示词
        full_prompt = self.build_full_prompt(user_input, history)
        
        print(f"完整提示词长度: {len(full_prompt)}字")
        
        # 生成回复
        response = await self.generate(full_prompt)
        
        if response:
            print(f"LLM回复: {response[:100]}...")
        else:
            print("LLM返回空回复")
        
        return response