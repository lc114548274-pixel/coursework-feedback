"""两种实际推理服务的环境配置。密钥不进入 repr、页面或本地模型请求。"""
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

CONFIG_VERSION = '2026-11-02-team-demo'

DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEEPSEEK_MODEL = 'deepseek-flash'
LOCAL_MODEL = 'coursework-qwen3:8b'

def local_inference_enabled():
    return os.getenv('OLLAMA_ENABLED', 'true').strip().lower() not in ('false', '0', 'no', 'off')

@dataclass(frozen=True)
class ProviderConfig:
    mode: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout: float
    num_ctx: int = 8192
    max_tokens: int = 4096
    enabled: bool = True

    @classmethod
    def from_environment(cls, mode):
        local = mode == 'ollama'
        try:
            timeout = float(os.getenv('OLLAMA_TIMEOUT' if local else 'AI_TIMEOUT', '180' if local else '60'))
            if not 1 <= timeout <= 600:
                raise ValueError()
        except ValueError:
            raise ValueError(('OLLAMA_TIMEOUT' if local else 'AI_TIMEOUT') + ' 必须是 1～600 秒') from None
        try:
            num_ctx = int(os.getenv('OLLAMA_NUM_CTX', '8192')) if local else 8192
            max_tokens = int(os.getenv('OLLAMA_MAX_TOKENS', '4096')) if local else 4096
            if local and (not 4096 <= num_ctx <= 131072 or not 512 <= max_tokens <= 8192 or max_tokens + 2048 >= num_ctx):
                raise ValueError()
        except ValueError:
            raise ValueError('Ollama 上下文须为 4096～131072，输出须为 512～8192，且至少预留 2048 上下文空间') from None
        return cls(mode=mode,
            base_url=os.getenv('OLLAMA_BASE_URL' if local else 'API_BASE_URL',
                               'http://127.0.0.1:11434' if local else DEEPSEEK_BASE_URL).rstrip('/'),
            model=os.getenv('OLLAMA_MODEL' if local else 'AI_MODEL', LOCAL_MODEL if local else DEEPSEEK_MODEL),
            api_key='' if local else os.getenv('API_KEY', '').strip(), timeout=timeout, num_ctx=num_ctx, max_tokens=max_tokens,
            enabled=local_inference_enabled() if local else True)

def migrate_legacy_local_environment():
    """旧进程曾把 Ollama 写入 API_*，只迁移明确的本机地址，保留 Key。"""
    try:
        url = urlsplit(os.getenv('API_BASE_URL', ''))
    except ValueError:
        return
    if url.hostname not in ('localhost', '127.0.0.1', '::1'):
        return
    os.environ.setdefault('OLLAMA_BASE_URL', os.environ['API_BASE_URL'])
    os.environ.setdefault('OLLAMA_MODEL', os.getenv('AI_MODEL', LOCAL_MODEL))
    os.environ.setdefault('OLLAMA_TIMEOUT', os.getenv('AI_TIMEOUT', '180'))
    os.environ['API_BASE_URL'] = DEEPSEEK_BASE_URL
    os.environ['AI_MODEL'] = DEEPSEEK_MODEL
    os.environ['AI_TIMEOUT'] = '60'
