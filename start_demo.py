"""同学电脑的启动入口：准备独立环境、检查配置、启动页面；不处理或保存作业。"""
import argparse
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent

def prepare_runtime():
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10+ is required; Python 3.12 is recommended.')
    runtime = ROOT/'.demo_venv'
    executable = runtime/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not executable.is_file():
        print('Preparing isolated Python environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(runtime)
    requirements = ROOT/'requirements-demo.txt'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = runtime/'.requirements.sha256'
    if not stamp.exists() or stamp.read_text() != digest:
        print('Installing dependencies. Internet is needed on first launch...', flush=True)
        subprocess.run([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check', '--quiet',
                        '-r', str(requirements)], check=True, cwd=ROOT)
        stamp.write_text(digest)
    return executable

def check_configuration(executable):
    if not (ROOT/'.env').is_file():
        raise RuntimeError('The bundled .env file is missing. Extract the complete team ZIP first.')
    code = '''from dotenv import load_dotenv
load_dotenv('.env', override=True)
import streamlit
from core.config import ProviderConfig
external = ProviderConfig.from_environment('real')
assert external.api_key, 'DeepSeek API_KEY is missing'
assert external.base_url.startswith('https://'), 'DeepSeek HTTPS endpoint is required'
print('DeepSeek configuration ready; key is configured (not displayed).')
print('Local AI enabled:', ProviderConfig.from_environment('ollama').enabled)
'''
    subprocess.run([str(executable), '-c', code], check=True, cwd=ROOT)

def available_port(preferred):
    for port in range(preferred, min(preferred + 20, 65536)):
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
            return port
        except OSError:
            continue
    raise RuntimeError('No free local port. Close a previous demo and try again.')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='prepare dependencies and check configuration only')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65515:
        raise RuntimeError('Port must be between 1024 and 65515.')
    executable = prepare_runtime()
    check_configuration(executable)
    if args.check:
        print('READY: launch the demo without editing API settings.', flush=True)
        return
    port = available_port(args.port)
    environment = os.environ.copy()
    environment['TEAM_DEMO'] = 'true'
    server = subprocess.Popen([str(executable), '-m', 'streamlit', 'run', str(ROOT/'app.py'),
        '--server.headless', 'true', '--server.address', '127.0.0.1', '--server.port', str(port)], cwd=ROOT, env=environment)
    address = f'http://127.0.0.1:{port}/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError('The application stopped before becoming ready.')
            try:
                with opener.open(address + '_stcore/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.3)
        else:
            raise RuntimeError('Application startup timed out.')
        print('Open: ' + address + '\nKeep this window open; press Ctrl+C to stop.', flush=True)
        if not args.no_browser:
            webbrowser.open(address)
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print('Startup failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
