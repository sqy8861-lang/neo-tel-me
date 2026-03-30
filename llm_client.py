from typing import Optional
from openai import AsyncOpenAI
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
        self.client = None
        self.system_prompt = ""
        self.memory_prompt = ""
    
    async def initialize(self):
        """初始化客户端"""
        # 使用 OpenAI SDK，支持自定义 base_url
        self.client = AsyncOpenAI(
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url
        )
        print("LLM客户端初始化完成")
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()
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
4. 回复要简洁，适合语音对话。
5. 不要重复历史对话中的内容

【约束】
1. 仅可在需要时使用以下感叹词标签：(laughs)(chuckle)(coughs)(clear-throat)(groans)(breath)(pant)(inhale)(exhale)(gasps)(sniffs)(sighs)(snorts)(burps)(lip-smacking)(humming)(hissing)(emm)(sneezes)。
2. 使用标签时必须其是英文且括号为英文括号。
3. 禁止出现除上述标签以外的带括号的表达，禁止其他形式的非对话内容。

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
        if not self.client:
            await self.initialize()
        
        max_tokens = max_tokens or self.config.model.max_tokens
        
        try:
            # 使用 OpenAI SDK 调用 API
            response = await self.client.chat.completions.create(
                model=self.config.model.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.model.temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                print("API返回空结果")
                return ""
        except Exception as e:
            print(f"LLM生成失败: {e}")
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
