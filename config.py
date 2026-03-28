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
        """
        加载配置文件
        """
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = toml.load(f)

            # 插件基础配置
            self.plugin = config_data.get('plugin', {})
            
            # 阿里云ASR配置
            self.aliyun_asr = config_data.get('aliyun_asr', {})
            self.aliyun_asr_access_key_id = self.aliyun_asr.get('access_key_id', '')
            self.aliyun_asr_access_key_secret = self.aliyun_asr.get('access_key_secret', '')
            self.aliyun_asr_appkey = self.aliyun_asr.get('appkey', '')
            self.aliyun_asr_sample_rate = self.aliyun_asr.get('sample_rate', 16000)
            self.aliyun_asr_format = self.aliyun_asr.get('format', 'wav')

            # MiniMax TTS配置
            self.minimax_tts = config_data.get('minimax_tts', {})
            self.minimax_tts_api_key = self.minimax_tts.get('api_key', '')
            self.minimax_tts_voice_id = self.minimax_tts.get('voice_id', 'female-tianmei')
            self.minimax_tts_model = self.minimax_tts.get('model', 'speech-01')
            self.minimax_tts_speed = self.minimax_tts.get('speed', 1.0)
            self.minimax_tts_volume = self.minimax_tts.get('volume', 1.0)
            self.minimax_tts_pitch = self.minimax_tts.get('pitch', 1.0)
            self.minimax_tts_sample_rate = self.minimax_tts.get('sample_rate', 24000)

            # 音频配置
            self.audio = config_data.get('audio', {})
            self.audio_sample_rate = self.audio.get('sample_rate', 16000)
            self.audio_chunk = self.audio.get('chunk', 1024)
            self.audio_vad_threshold = self.audio.get('vad_threshold', 0.02)

            # LLM配置
            self.llm = config_data.get('llm', {})
            self.llm_model = self.llm.get('model', {})
            self.llm_model_provider = self.llm_model.get('provider', 'openai')
            self.llm_model_name = self.llm_model.get('model_name', 'gpt-4')
            self.llm_model_api_key = self.llm_model.get('api_key', '')
            self.llm_model_base_url = self.llm_model.get('base_url', 'https://api.openai.com/v1')
            self.llm_model_temperature = self.llm_model.get('temperature', 0.7)
            self.llm_model_max_tokens = self.llm_model.get('max_tokens', 1000)
            
            self.llm_prompt = self.llm.get('prompt', {})
            self.llm_prompt_personality_prompt = self.llm_prompt.get('personality_prompt', '')
            self.llm_prompt_memory_prompt = self.llm_prompt.get('memory_prompt', '')
            self.llm_prompt_max_history = self.llm_prompt.get('max_history', 4)
            
            self.llm_memory = self.llm.get('memory', {})
            self.llm_memory_recent_count = self.llm_memory.get('recent_count', 5)
            self.llm_memory_important_only = self.llm_memory.get('important_only', True)
            
            # WebSocket配置
            self.websocket = config_data.get('websocket', {})
            self.websocket_enabled = self.websocket.get('enabled', False)
            self.websocket_host = self.websocket.get('host', '0.0.0.0')
            self.websocket_port = self.websocket.get('port', 8766)
            self.websocket_audio_format = self.websocket.get('audio_format', 'pcm')
        else:
            # 默认配置
            self.plugin = {}
            self.aliyun_asr = {}
            self.aliyun_asr_access_key_id = ''
            self.aliyun_asr_access_key_secret = ''
            self.aliyun_asr_appkey = ''
            self.aliyun_asr_sample_rate = 16000
            self.aliyun_asr_format = 'wav'

            self.minimax_tts = {}
            self.minimax_tts_api_key = ''
            self.minimax_tts_voice_id = 'female-tianmei'
            self.minimax_tts_model = 'speech-01'
            self.minimax_tts_speed = 1.0
            self.minimax_tts_volume = 1.0
            self.minimax_tts_pitch = 1.0
            self.minimax_tts_sample_rate = 24000

            self.audio = {}
            self.audio_sample_rate = 16000
            self.audio_chunk = 1024
            self.audio_vad_threshold = 0.02

            self.llm = {}
            self.llm_model = {}
            self.llm_model_provider = 'openai'
            self.llm_model_name = 'gpt-4'
            self.llm_model_api_key = ''
            self.llm_model_base_url = 'https://api.openai.com/v1'
            self.llm_model_temperature = 0.7
            self.llm_model_max_tokens = 1000
            
            self.llm_prompt = {}
            self.llm_prompt_personality_prompt = ''
            self.llm_prompt_memory_prompt = ''
            self.llm_prompt_max_history = 4
            
            self.llm_memory = {}
            self.llm_memory_recent_count = 5
            self.llm_memory_important_only = True
            
            # WebSocket默认配置
            self.websocket = {}
            self.websocket_enabled = False
            self.websocket_host = '0.0.0.0'
            self.websocket_port = 8766
            self.websocket_audio_format = 'pcm'
