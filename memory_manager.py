from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class MemoryItem:
    """记忆项"""
    content: str
    importance: float  # 重要性分数 0-1
    timestamp: str
    type: str  # recent, important, relationship


class MemoryManager:
    """记忆管理器：与booku_memory集成"""
    
    def __init__(self):
        """初始化记忆管理器"""
        self.booku_memory_service = None
        self.recent_memories: List[MemoryItem] = []
        self.important_memories: List[MemoryItem] = []
        self.relationship_info: str = ""
        self.memory_prompt: str = ""
    
    def initialize(self, booku_memory_service=None):
        """
        初始化记忆管理器
        
        Args:
            booku_memory_service: booku_memory服务实例
        """
        self.booku_memory_service = booku_memory_service
        print("记忆管理器初始化完成")
    
    async def fetch_recent_memories(self, count: int = 5) -> List[MemoryItem]:
        """
        获取近期记忆
        
        Args:
            count: 记忆数量
            
        Returns:
            List[MemoryItem]: 近期记忆列表
        """
        # 直接返回空列表，不再使用booku_memory服务
        return []
    
    async def fetch_important_memories(self, count: int = 3) -> List[MemoryItem]:
        """
        获取重要记忆
        
        Args:
            count: 记忆数量
            
        Returns:
            List[MemoryItem]: 重要记忆列表
        """
        # 直接返回空列表，不再使用booku_memory服务
        return []
    
    async def fetch_relationship_info(self) -> str:
        """
        获取机器人与对话人物的关系信息
        
        Returns:
            str: 关系信息
        """
        # 直接返回默认关系，不再使用booku_memory服务
        return "用户是辞安的哥哥，关系亲密，辞安对他有特殊依赖。"
    
    async def generate_memory_prompt(self, llm_client=None, user_nickname: str = "") -> str:
        """
        生成记忆提示词（200字左右）
        
        Args:
            llm_client: LLM客户端（可选）
            user_nickname: 用户昵称，用于搜索记忆
            
        Returns:
            str: 记忆提示词
        """
        # 获取记忆信息
        recent_memories = await self.fetch_recent_memories()
        important_memories = await self.fetch_important_memories()
        relationship_info = await self.fetch_relationship_info()
        
        # 如果有用户昵称，使用用户昵称搜索记忆
        if user_nickname:
            search_memories = await self.search_memories_by_keyword(user_nickname)
        else:
            search_memories = []
        
        # 构建原始记忆内容
        memory_content = f"""关系信息：{relationship_info}

近期记忆：
{self._format_memories(recent_memories)}

重要记忆：
{self._format_memories(important_memories)}

用户相关记忆：
{self._format_memories(search_memories)}"""
        
        print(f"原始记忆内容: {len(memory_content)}字")
        
        # 如果有LLM客户端，精炼为200字
        if llm_client:
            try:
                refine_prompt = f"""请将以下记忆信息精炼为200字左右的提示词，用于控制机器人在连麦时的态度和回忆：

{memory_content}

要求：
1. 保持在200字左右
2. 保留关键关系信息
3. 保留重要记忆的情感价值
4. 语言简洁，适合作为LLM的上下文提示词"""

                response = await llm_client.generate(refine_prompt, max_tokens=300)
                
                if response:
                    self.memory_prompt = response
                    print(f"✅ 记忆提示词精炼完成: {len(self.memory_prompt)}字")
                    return self.memory_prompt
            except Exception as e:
                print(f"精炼记忆提示词失败: {e}")
        
        # 没有LLM客户端或精炼失败，直接使用前200字
        self.memory_prompt = memory_content[:200]
        print(f"使用原始记忆内容: {len(self.memory_prompt)}字")
        return self.memory_prompt
    
    def _format_memories(self, memories: List[MemoryItem]) -> str:
        """
        格式化记忆列表
        
        Args:
            memories: 记忆列表
            
        Returns:
            str: 格式化后的记忆文本
        """
        if not memories:
            return "暂无记忆"
        
        formatted = []
        for memory in memories:
            formatted.append(f"- {memory.content}")
        
        return '\n'.join(formatted)
    
    def get_memory_prompt(self) -> str:
        """
        获取记忆提示词
        
        Returns:
            str: 记忆提示词
        """
        return self.memory_prompt
    
    def set_memory_prompt(self, prompt: str):
        """
        设置记忆提示词
        
        Args:
            prompt: 记忆提示词
        """
        self.memory_prompt = prompt
        print(f"设置记忆提示词: {len(self.memory_prompt)}字")