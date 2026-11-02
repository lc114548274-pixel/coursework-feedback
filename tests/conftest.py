"""测试与开发者本机的 .env / 密钥配置隔离，单测绝不访问真实模型。"""
import pytest
import dotenv

@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in ('AI_MODE', 'AI_MODEL', 'API_KEY', 'API_BASE_URL', 'AI_TIMEOUT',
                 'OLLAMA_BASE_URL', 'OLLAMA_MODEL', 'OLLAMA_TIMEOUT', 'OLLAMA_NUM_CTX', 'OLLAMA_MAX_TOKENS',
                 'OLLAMA_ENABLED', 'TEAM_DEMO'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args, **kwargs: False)
