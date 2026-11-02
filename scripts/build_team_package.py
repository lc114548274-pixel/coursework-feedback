"""生成含共享 .env 的团队私用包；密钥始终从环境读取，不写进源码。"""
import os
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import ProviderConfig

def build_team_zip(output):
    load_dotenv(ROOT/'.env')
    config = ProviderConfig.from_environment('real')
    if not config.api_key:
        raise ValueError('配置 API_KEY 后才能制作可直接演示的团队包')
    settings = {'TEAM_DEMO': 'true', 'AI_MODE': 'real', 'API_BASE_URL': config.base_url,
                'API_KEY': config.api_key, 'AI_MODEL': config.model, 'AI_TIMEOUT': '90',
                'OLLAMA_ENABLED': 'true', 'OLLAMA_BASE_URL': 'http://127.0.0.1:11434',
                'OLLAMA_MODEL': 'coursework-qwen3:8b', 'OLLAMA_TIMEOUT': '180',
                'OLLAMA_NUM_CTX': '8192', 'OLLAMA_MAX_TOKENS': '4096'}
    if any('\n' in value or '\r' in value for value in settings.values()):
        raise ValueError('环境配置不能包含换行')
    excluded = {'.git', '.venv', '.demo_venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist'}
    prefix = Path('coursework_feedback_team')
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for directory, subdirs, files in os.walk(ROOT):
            subdirs[:] = [name for name in subdirs if name not in excluded]
            for name in files:
                if name == '.env' or name.lower().endswith(('.zip', '.7z', '.rar')):
                    continue
                path = Path(directory)/name
                archive.write(path, (prefix/path.relative_to(ROOT)).as_posix())
        archive.writestr((prefix/'.env').as_posix(), '\n'.join(key + '=' + value for key, value in settings.items()) + '\n')
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.read((prefix/'.env').as_posix()).decode().splitlines()[0] == 'TEAM_DEMO=true'
    return output

if __name__ == '__main__':
    output = build_team_zip(ROOT.parent/'coursework_feedback_team.zip')
    print('Team demo package verified: ' + str(output))
    print('Shared API environment included; local AI enabled; key not displayed.')
