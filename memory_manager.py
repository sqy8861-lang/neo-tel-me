from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path
import asyncio


@dataclass
class MemoryItem:
    """记忆项"""
    content: str
    importance: float
    timestamp: str
    type: str


class MemoryManager:
    """记忆管理器：基于 stream_id 查询消息历史 + 用户昵称搜索记忆"""
    
    def __init__(self):
        """初始化记忆管理器"""
        self.relationship_info: str = "用户是辞安的哥哥，关系亲密，辞安对他有特殊依赖。"
        self.memory_prompt: str = ""
    
    async def fetch_messages_by_stream_id(self, stream_id: str, limit: int = 50) -> List[dict]:
        """
        根据 stream_id 从 mofox.db 查询最近的消息记录
        
        Args:
            stream_id: 聊天流 ID
            limit: 最大消息数量，默认 50 条
            
        Returns:
            List[dict]: 消息列表，每条消息包含 role, content, time
        """
        if not stream_id:
            print("stream_id 为空，无法查询消息")
            return []
        
        try:
            from src.kernel.db import QueryBuilder
            from src.core.models.sql_alchemy import Messages
            
            query = (
                QueryBuilder(Messages)
                .filter(stream_id=stream_id)
                .filter(message_type="text")
                .order_by("-time")
            )
            messages = await query.limit(limit).all()
            
            if not messages:
                print(f"stream_id={stream_id} 无消息记录")
                return []
            
            result = []
            for msg in messages:
                role = "用户" if msg.person_id != "bot" else "AI"
                content = msg.content or msg.processed_plain_text or ""
                if content.strip():
                    result.append({
                        "role": role,
                        "content": content.strip(),
                        "time": msg.time
                    })
            
            print(f"从 stream_id={stream_id[:16]}... 查询到 {len(result)} 条消息")
            return result
            
        except Exception as e:
            print(f"查询消息失败: {e}")
            return []
    
    async def search_memories_by_keyword(self, keyword: str) -> List[MemoryItem]:
        """
        根据关键词从 booku_memory 数据库搜索记忆
        
        Args:
            keyword: 搜索关键词（用户昵称）
            
        Returns:
            List[MemoryItem]: 搜索到的记忆列表
        """
        import sqlite3
        
        db_path = Path("data/booku_memory/metadata.db")
        if not db_path.exists():
            print(f"booku_memory 数据库不存在: {db_path}")
            return []
        
        if not keyword or not keyword.strip():
            return []
        
        print(f"从 booku_memory 搜索关键字 '{keyword}' 的记忆...")
        
        search_memories = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT memory_id, title, content, bucket, folder_id, created_at 
                FROM booku_memory_records 
                WHERE title LIKE ? AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT 10
            """, (f"%{keyword}%",))
            
            records = cursor.fetchall()
            
            for record in records:
                memory_id, title, content, bucket, folder_id, created_at = record
                memory_item = MemoryItem(
                    content=f"{title}: {content}",
                    importance=0.8,
                    timestamp=str(created_at),
                    type="important"
                )
                search_memories.append(memory_item)
            
            print(f"找到 {len(search_memories)} 条相关记忆")
            
        except Exception as e:
            print(f"搜索记忆失败: {e}")
        finally:
            conn.close()
        
        return search_memories
    
    def _format_messages_for_summary(self, messages: List[dict]) -> str:
        """
        格式化消息列表用于总结
        
        Args:
            messages: 消息列表
            
        Returns:
            str: 格式化后的对话文本
        """
        if not messages:
            return "暂无对话记录"
        
        formatted = []
        for msg in messages:
            role = msg.get("role", "未知")
            content = msg.get("content", "")
            if content:
                formatted.append(f"{role}: {content}")
        
        return '\n'.join(formatted)
    
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
    
    async def generate_memory_prompt(
        self, 
        llm_client=None, 
        stream_id: str = "",
        user_nickname: str = ""
    ) -> str:
        """
        生成记忆提示词
        
        Args:
            llm_client: LLM客户端（用于精炼记忆）
            stream_id: 聊天流 ID，用于查询消息历史
            user_nickname: 用户昵称，用于搜索记忆
            
        Returns:
            str: 记忆提示词（对话精炼200字 + 用户记忆精炼200字）
        """
        conversation_text = ""
        user_memories_text = ""
        
        if stream_id:
            messages = await self.fetch_messages_by_stream_id(stream_id, limit=50)
            conversation_text = self._format_messages_for_summary(messages)
        
        if user_nickname:
            user_memories = await self.search_memories_by_keyword(user_nickname)
            user_memories_text = self._format_memories(user_memories)
        
        async def refine_conversation() -> str:
            if not llm_client or not conversation_text:
                return conversation_text[:200] if conversation_text else ""
            try:
                user_label = f"与{user_nickname}" if user_nickname else "与用户"
                prompt = f"""请分析以下对话记录，提取关键信息，生成200字左右的总结。

对话记录：
{conversation_text}

要求：
1. 总结{user_label}的互动特点、情感状态、重要话题
2. 语言简洁
3. 控制在200字左右"""
                response = await llm_client.generate(prompt, max_tokens=300)
                if response:
                    print(f"✅ 对话记录精炼完成: {len(response)}字")
                    return response
            except Exception as e:
                print(f"精炼对话记录失败: {e}")
            return conversation_text[:200] if conversation_text else ""
        
        async def refine_user_memories() -> str:
            if not user_memories_text or user_memories_text == "暂无记忆":
                return ""
            if not llm_client:
                return user_memories_text[:200]
            try:
                prompt = f"""请将以下用户相关记忆整合为200字左右的摘要。

记忆内容：
{user_memories_text}

要求：
1. 保留关键信息和情感价值
2. 语言简洁
3. 最多200字"""
                response = await llm_client.generate(prompt, max_tokens=300)
                if response:
                    print(f"✅ 用户记忆精炼完成: {len(response)}字")
                    return response
            except Exception as e:
                print(f"精炼用户记忆失败: {e}")
            return user_memories_text[:200]
        
        conversation_summary, user_memories_summary = await asyncio.gather(
            refine_conversation(),
            refine_user_memories()
        )
        
        parts = []
        if conversation_summary:
            parts.append(f"【对话记忆】\n{conversation_summary}")
        if user_memories_summary:
            parts.append(f"【用户记忆】\n{user_memories_summary}")
        
        if parts:
            self.memory_prompt = "\n\n".join(parts)
        else:
            self.memory_prompt = f"【关系】{self.relationship_info}"
        
        print(f"记忆提示词总长度: {len(self.memory_prompt)}字")
        return self.memory_prompt
    
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
