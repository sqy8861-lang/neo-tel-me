# Neo-tel-me

Neo-MoFox 实时语音对话插件，支持阿里云 ASR 语音识别、大语言模型对话和 MiniMax TTS 语音合成。

## 功能特性

- **实时语音识别**：基于阿里云 ASR，支持实时流式识别
- **智能对话生成**：支持 OpenAI / DeepSeek 等兼容 OpenAI API 的大模型
- **高质量语音合成**：MiniMax TTS，支持多种语音风格
- **语音打断**：用户说话时可打断 AI 回复
- **记忆系统**：实时判断消息价值并写入长期记忆
- **H5 连麦界面**：支持手机和电脑浏览器
- **WebSocket 实时通信**：低延迟双向音频传输

## 安装

将插件文件夹放入 Neo-MoFox 的 `plugins` 目录下：

```
Neo-MoFox/
└── plugins/
    └── neo_tel_me/
        ├── __init__.py
        ├── plugin.py
        ├── service.py
        ├── config.py
        └── ...
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置说明

配置文件位于 `config/plugins/neo_tel_me/config.toml`：

### 阿里云 ASR 配置

```toml
[aliyun_asr]
access_key_id = "your_access_key_id"
access_key_secret = "your_access_key_secret"
appkey = "your_appkey"
sample_rate = 16000
format = "pcm"
```

### MiniMax TTS 配置

```toml
[minimax_tts]
api_key = "your_api_key"
voice_id = "neo_cian2"          # 语音ID
model = "speech-2.6-turbo"      # TTS模型
sample_rate = 16000
format = "pcm"
speed = 1.0
volume = 1.0
pitch = 0
```

### LLM 配置

```toml
[llm.model]
provider = "DeepSeek"           # 模型提供商
model_name = "deepseek-chat"    # 模型名称
api_key = "your_api_key"
base_url = "https://api.deepseek.com"
temperature = 0.7
max_tokens = 1000

[llm.prompt]
personality_prompt = ""         # 性格提示词（可选，留空自动生成）
memory_prompt = ""              # 记忆提示词（可选）
max_history = 4                 # 保留最近对话轮数

[llm.memory]
recent_count = 5                # 近期记忆数量
important_only = true           # 只获取重要记忆
```

### WebSocket 配置（H5 模式）

```toml
[websocket]
enabled = true                  # 启用 WebSocket 模式
host = "0.0.0.0"
port = 8766
public_ip = ""                  # 公网IP（可选）
audio_format = "pcm"
use_ssl = false                 # 是否启用 HTTPS/WSS
ssl_cert = ""                   # SSL 证书路径（留空则自动生成自签名证书）
ssl_key = ""                    # SSL 私钥路径（留空则自动生成）
```

> **SSL 证书说明**：启用 `use_ssl = true` 时，如果 `ssl_cert` 和 `ssl_key` 为空，插件会自动生成自签名证书，首次访问浏览器会提示不安全，点击继续访问即可。

### 音频配置（本地模式）

```toml
[audio]
sample_rate = 16000
chunk = 512                     # 音频块大小
vad_threshold = 600             # 语音活动检测阈值
```

## 使用方法

### 触发连麦

在 Neo-MoFox 中发送包含 `#连麦` 标签的消息，AI 会返回 H5 连麦页面链接。

### H5 连麦流程

1. 点击 AI 返回的连麦链接
2. 浏览器请求麦克风权限
3. 点击「开始连麦」按钮
4. 开始语音对话
5. 点击「结束连麦」退出

### 记忆系统

连麦过程中，插件会自动判断消息是否值得写入长期记忆：

- 实时分析每条消息的内容价值
- 包含事实、偏好、关系变化等重要信息时自动记录
- 无需等待连麦结束

## 模块说明

| 文件 | 说明 |
|------|------|
| `plugin.py` | 插件入口，注册服务和动作 |
| `service.py` | 核心服务，协调各模块 |
| `config.py` | 配置定义 |
| `aliyun_asr.py` | 阿里云实时语音识别 |
| `minimax_tts.py` | MiniMax 语音合成 |
| `audio_manager.py` | 本地音频采集与播放 |
| `llm_client.py` | LLM 客户端封装 |
| `llm_config.py` | LLM 配置管理 |
| `prompt_refiner.py` | 提示词精炼 |
| `memory_manager.py` | 记忆管理 |
| `history_manager.py` | 对话历史管理 |
| `call_message_storage.py` | 连麦消息存储与记忆写入 |
| `websocket_handler.py` | WebSocket 服务 |
| `action.py` | 连麦触发动作 |
| `web/index.html` | H5 连麦页面 |

## 依赖说明

### 核心依赖

- `openai` - OpenAI API 客户端
- `websockets` - WebSocket 通信
- `pydantic` - 数据验证
- `toml` - 配置解析
- `json-repair` - JSON 修复解析
- `cryptography` - SSL 证书生成

### 本地模式依赖

- `pyaudio` - 音频采集与播放
- `numpy` - 音频数据处理
- `alibabacloud-nls-python-sdk` - 阿里云 ASR SDK

## 注意事项

1. 需要有效的阿里云 ASR、MiniMax TTS、LLM API 密钥
2. H5 模式需要服务器有公网 IP 或内网穿透
3. 建议使用 Python 3.10 或更高版本
4. 浏览器需支持 Web Audio API 和 MediaRecorder API

## 友情支持

如果你买雨云的服务器，可以用我的邀请码sqy8861支持一下我，帮助我的猫娘继续生活，感恩~

实在不行帮忙点个⭐也很感谢。

## 许可证

MIT License
