from src.core.components.base.action import BaseAction


class NeoTelMeAction(BaseAction):
    """Neo-tel-me Action：生成连麦H5页面链接"""

    action_name = "neo_tel_me"
    action_description = "生成Neo-tel-me连麦H5页面链接。当用户的消息中包含 '#连麦' 标签时，应该调用此动作来生成连麦页面链接。用户点击链接后可以开始语音对话。"

    chatter_allow: list[str] = []

    async def execute(self, action: str = "start") -> tuple[bool, str]:
        """执行Neo-tel-me动作

        Args:
            action: 动作类型，可选值：start（生成链接）
        """
        # 生成 H5 页面链接
        # 注意：实际部署时需要替换为真实的服务器地址
        web_url = "http://localhost:8765/web/index.html"
        
        if action == "start":
            return True, f"🎙️ 连麦功能已准备就绪！请点击以下链接开始连麦：\n{web_url}\n\n点击链接后，在打开的页面中点击'开始连麦'按钮即可开始语音对话。"
        
        else:
            return False, f"未知的动作类型: {action}"