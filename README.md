# Neo-tel-me

一个基于Python的实时语音对话AI助手，支持语音识别、大语言模型对话和语音合成。

## 功能特性

- 实时语音识别（阿里云ASR）
- 智能对话生成（支持OpenAI/Anthropic等大模型）
- 高质量语音合成（MiniMax TTS）
- 语音活动检测（VAD）和用户打断支持
- 个性化提示词精炼
- 记忆管理和上下文保持
- 对话历史管理
- H5页面连麦界面（支持手机和电脑）
- WebSocket实时通信
- HTTP静态文件服务

## 系统架构

```
Neo-tel-me
├── ASR模块（语音识别）
├── LLM模块（对话生成）
│   ├── 配置管理
│   ├── 提示词精炼
│   ├── 记忆管理
│   └── 历史记录管理
├── TTS模块（语音合成）
├── 音频管理（采集/播放）
├── WebSocket服务器（实时通信）
└── HTTP服务器（H5页面服务）
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### 1. 阿里云ASR配置

在配置文件中设置阿里云ASR的appkey：
```python
aliyun_asr:
    appkey: "your_appkey"
    sample_rate: 16000
    format: "wav"
```

### 2. MiniMax TTS配置

设置MiniMax TTS的API密钥和语音参数：
```python
minimax_tts:
    api_key: "your_api_key"
    voice_id: "female-tianmei"
    model: "speech-01"
    speed: 1.0
    volume: 1.0
    pitch: 1.0
    sample_rate: 24000
```

### 3. LLM配置

配置大语言模型参数：
```python
llm:
    model:
        provider: "openai"  # 或 "anthropic"
        model_name: "gpt-4"
        api_key: "your_api_key"
        base_url: "https://api.openai.com/v1"
        temperature: 0.7
        max_tokens: 1000
```

## 使用方法

### H5页面连麦

1. 在Neo-MoFox中发送包含 `#连麦` 标签的消息
2. 点击机器人回复的H5页面链接
3. 在页面中点击"开始连麦"按钮
4. 开始与AI进行语音对话

### 基本使用

```python
import asyncio
from service import NeoTelMeService
from config import Config

async def main():
    # 加载配置
    config = Config.load("config.toml")
    
    # 创建服务
    service = NeoTelMeService(config)
    
    # 启动服务
    if await service.start():
        print("服务已启动，开始对话...")
        
        # 保持运行
        while service.is_service_running():
            await asyncio.sleep(1)
    
    # 停止服务
    await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### LLM模块独立使用

```python
from llm_config import LLMConfig
from llm_client import LLMClient
from prompt_refiner import PromptRefiner
from memory_manager import MemoryManager
from history_manager import HistoryManager

# 初始化LLM配置
config = LLMConfig()
llm_client = LLMClient(config)
await llm_client.initialize()

# 设置提示词
llm_client.set_system_prompt("你是辞安，用户的傲娇系温柔守护者。")
llm_client.set_memory_prompt("用户是辞安的哥哥，关系亲密。")

# 生成回复
history = "用户: 你好"
user_input = "你好"
reply = await llm_client.generate_response(user_input, history)
print(f"AI回复: {reply}")
```

## 核心模块说明

### 1. ASR模块（aliyun_asr.py）

负责实时语音识别，将用户语音转换为文本。

### 2. LLM模块

- **llm_config.py**: LLM配置管理
- **llm_client.py**: LLM客户端，支持OpenAI和Anthropic API
- **prompt_refiner.py**: 提示词精炼，将性格描述精炼为200字提示词
- **memory_manager.py**: 记忆管理，集成booku_memory获取对话上下文
- **history_manager.py**: 历史记录管理，维护最近4条对话记录

### 3. TTS模块（minimax_tts.py）

负责将AI回复转换为语音，支持流式播放。

### 4. 音频管理模块（audio_manager.py）

负责音频采集、播放和语音活动检测。

### 5. WebSocket服务器（websocket_server.py）

处理H5页面的实时音频通信。

### 6. HTTP服务器（http_server.py）

提供H5页面静态文件服务。

## 工作流程

### H5页面连麦流程

1. **用户触发**：在QQ中发送包含 `#连麦` 标签的消息
2. **生成链接**：大模型调用 `neo_tel_me` 动作，生成H5页面链接
3. **用户打开链接**：用户点击链接，打开H5页面
4. **初始化**：H5页面连接WebSocket服务器，显示"初始化完成"
5. **开始连麦**：用户点击"开始连麦"按钮，页面请求麦克风权限
6. **实时对话**：
   - 页面采集音频并发送到WebSocket服务器
   - WebSocket服务器将音频发送到阿里云ASR
   - ASR识别结果发送到LLM生成回复
   - LLM回复通过MiniMax TTS转换为语音
   - 语音发送回H5页面并播放
7. **结束连麦**：用户点击"结束连麦"按钮或关闭页面

### 本地服务流程

1. **初始化阶段**
   - 加载配置文件
   - 初始化LLM组件
   - 生成性格提示词和记忆提示词

2. **连麦启动阶段**
   - 初始化音频设备
   - 连接ASR服务
   - 准备TTS服务

3. **语音对话阶段**
   - 采集用户语音
   - ASR识别为文本
   - LLM生成回复（性格+记忆+历史+用户输入）
   - TTS合成语音
   - 播放AI回复

## 测试

运行测试脚本：
```bash
python test_llm_module.py
```

## 注意事项

1. 需要有效的API密钥才能使用ASR、TTS和LLM服务
2. 确保麦克风和扬声器正常工作
3. 建议使用Python 3.8或更高版本
4. 首次使用需要安装音频驱动和依赖库
5. H5页面需要浏览器支持Web Audio API和MediaRecorder API

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题，请提交Issue或联系维护者。