from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DialogueItem:
    """对话项"""

    role: str  # user, assistant
    content: str
    timestamp: datetime


class HistoryManager:
    """历史记录管理器"""

    def __init__(self, max_history: int = 4):
        """
        初始化历史记录管理器

        Args:
            max_history: 最大历史记录数量
        """
        self.max_history = max_history
        self.history: List[DialogueItem] = []

    def add_user_message(self, content: str):
        """
        添加用户消息

        Args:
            content: 用户消息内容
        """
        dialogue = DialogueItem(role="user", content=content, timestamp=datetime.now())
        self.history.append(dialogue)
        self._trim_history()
        print(f"添加用户消息: {content[:50]}...")

    def add_assistant_message(self, content: str):
        """
        添加助手消息

        Args:
            content: 助手消息内容
        """
        dialogue = DialogueItem(
            role="assistant", content=content, timestamp=datetime.now()
        )
        self.history.append(dialogue)
        self._trim_history()
        print(f"添加助手消息: {content[:50]}...")

    def _trim_history(self):
        """
        修剪历史记录，保持在最大数量内
        """
        if len(self.history) > self.max_history:
            removed = len(self.history) - self.max_history
            self.history = self.history[-self.max_history :]
            print(f"修剪历史记录，移除 {removed} 条旧记录")

    def get_recent_history(self, count: Optional[int] = None) -> List[DialogueItem]:
        """
        获取最近的历史记录

        Args:
            count: 要获取的记录数量，None表示全部

        Returns:
            List[DialogueItem]: 历史记录列表
        """
        if count is None:
            return self.history

        return self.history[-count:]

    def format_for_llm(self) -> str:
        """
        格式化历史记录用于LLM

        Returns:
            str: 格式化后的历史记录文本
        """
        if not self.history:
            return "暂无对话历史"

        formatted = []
        for dialogue in self.history:
            role_name = "用户" if dialogue.role == "user" else "AI"
            formatted.append(f"{role_name}: {dialogue.content}")

        return "\n".join(formatted)

    def clear_history(self):
        """
        清空历史记录
        """
        self.history.clear()
        print("历史记录已清空")

    def get_history_count(self) -> int:
        """
        获取历史记录数量

        Returns:
            int: 历史记录数量
        """
        return len(self.history)

    def is_empty(self) -> bool:
        """
        检查历史记录是否为空

        Returns:
            bool: 是否为空
        """
        return len(self.history) == 0
