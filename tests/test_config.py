import pytest
import httpx
from core.config import ProviderConfig, migrate_legacy_local_environment
from core.ai_client import AIClient, AIError

def test_external_and_local_settings_are_independent(monkeypatch):
    monkeypatch.setenv('API_BASE_URL', 'https://api.deepseek.com')
    monkeypatch.setenv('API_KEY', 'private-placeholder')
    monkeypatch.setenv('AI_MODEL', 'deepseek-flash')
    monkeypatch.setenv('AI_TIMEOUT', '45')
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
    monkeypatch.setenv('OLLAMA_MODEL', 'coursework-qwen3:8b')
    monkeypatch.setenv('OLLAMA_TIMEOUT', '120')
    external, local = AIClient('real'), AIClient('ollama')
    assert (external.base, external.model, external.timeout) == ('https://api.deepseek.com', 'deepseek-flash', 45)
    assert (local.base, local.model, local.timeout) == ('http://127.0.0.1:11434', 'coursework-qwen3:8b', 120)
    assert external.key == 'private-placeholder' and local.key == ''
    assert 'private-placeholder' not in repr(ProviderConfig.from_environment('real'))

def test_invalid_local_options_do_not_break_external_api(monkeypatch):
    monkeypatch.setenv('API_KEY', 'placeholder')
    monkeypatch.setenv('OLLAMA_TIMEOUT', 'invalid')
    monkeypatch.setenv('OLLAMA_NUM_CTX', 'bad')
    assert AIClient('real').model == 'deepseek-flash'
    with pytest.raises(AIError, match='OLLAMA_TIMEOUT'): AIClient('ollama')

def test_legacy_local_configuration_migration_preserves_key(monkeypatch):
    monkeypatch.setenv('API_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('AI_MODEL', 'previous-local-model')
    monkeypatch.setenv('AI_TIMEOUT', '150')
    monkeypatch.setenv('API_KEY', 'keep-existing-secret')
    migrate_legacy_local_environment()
    external, local = ProviderConfig.from_environment('real'), ProviderConfig.from_environment('ollama')
    assert external.base_url == 'https://api.deepseek.com'
    assert external.model == 'deepseek-flash' and external.api_key == 'keep-existing-secret'
    assert local.model == 'previous-local-model' and local.timeout == 150

def test_model_information_is_queried_not_hardcoded(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'another-local-model:4b')
    captured = []
    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={'details': {'parameter_size': '4.1B', 'quantization_level': 'Q5_K_M'},
            'model_info': {'general.architecture': 'qwen3', 'qwen3.context_length': 4096}})
    client = AIClient('ollama', httpx.MockTransport(handler))
    description = client.describe_local_model()
    assert description == {'architecture': 'qwen3', 'parameter_size': '4.1B', 'quantization': 'Q5_K_M',
                           'model_context': 4096, 'context': 4096}
    assert len(captured) == 1 and captured[0].url.path == '/api/show'
    assert 'authorization' not in captured[0].headers

def test_metadata_failure_is_user_readable():
    client = AIClient('ollama', httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(AIError, match='暂未读取到'): client.describe_local_model()
