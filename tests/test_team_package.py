from pathlib import Path
from io import StringIO
from uuid import uuid4
from zipfile import ZipFile
import pytest
import httpx
from dotenv import dotenv_values
from core.ai_client import AIClient, AIError
from core.config import ProviderConfig

def test_team_profile_blocks_local_inference_before_network(monkeypatch):
    monkeypatch.setenv('OLLAMA_ENABLED', 'false')
    assert ProviderConfig.from_environment('ollama').enabled is False
    def handler(request):
        pytest.fail('团队包不得向本地 Ollama 发送请求')
    with pytest.raises(AIError, match='本地 AI 不可用'):
        AIClient('ollama', httpx.MockTransport(handler))
    monkeypatch.setenv('API_KEY', 'test-placeholder')
    assert AIClient('real').mode == 'real'

def test_team_zip_includes_shared_environment_but_not_key_in_source(monkeypatch, tmp_path):
    from scripts import build_team_package as builder
    key = 'test-' + uuid4().hex
    monkeypatch.setenv('API_KEY', key)
    monkeypatch.setattr(builder, 'load_dotenv', lambda *args, **kwargs: False)
    target = builder.build_team_zip(tmp_path/'team.zip')
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        prefix = 'coursework_feedback_team/'
        settings = dotenv_values(stream=StringIO(archive.read(prefix+'.env').decode()))
        assert settings['AI_MODE'] == 'real' and settings['OLLAMA_ENABLED'] == 'true'
        assert settings['TEAM_DEMO'] == 'true' and settings['API_KEY'] == key
        assert settings['API_BASE_URL'] == 'https://api.deepseek.com'
        assert prefix+'启动演示.bat' in archive.namelist()
        assert prefix+'requirements-demo.txt' in archive.namelist()
        assert not any('.demo_venv/' in n or '__pycache__/' in n for n in archive.namelist())
        assert [n for n in archive.namelist() if key.encode() in archive.read(n)] == [prefix+'.env']

def test_team_package_requires_configured_key(monkeypatch, tmp_path):
    from scripts import build_team_package as builder
    monkeypatch.setattr(builder, 'load_dotenv', lambda *args, **kwargs: False)
    with pytest.raises(ValueError, match='API_KEY'):
        builder.build_team_zip(tmp_path/'team.zip')
