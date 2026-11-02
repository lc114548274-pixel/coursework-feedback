"""运行真实 Streamlit 脚本及控件事件，验证三页闭环。"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import json
import httpx
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(autouse=True)
def fake_provider(monkeypatch, isolated_configuration):
    """页面仍走两种真实客户端协议；单测只替换网络传输，不提供 mock 页面入口。"""
    import core.ai_client as ai_module
    from core.models import Document
    actual_class = ai_module.AIClient
    stub = actual_class('mock')
    criteria = stub.extract_criteria('要求')
    captured = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'details': {'parameter_size': '8.2B', 'quantization_level': 'Q4_K_M'},
                'model_info': {'general.architecture': 'qwen3', 'qwen3.context_length': 131072}})
        body = json.loads(request.content)
        payload = json.loads(body['messages'][1]['content'])
        captured.append((str(request.url), payload))
        if 'requirement' in payload:
            result = criteria
        elif 'paragraphs' in payload:
            result = stub.analyze(Document('x', 'x', paragraphs=[p['text'] for p in payload['paragraphs']]), criteria, {})
        else:
            result = stub.class_outline(payload['statistics'], criteria)
        if request.url.path == '/api/chat':
            return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': result.model_dump_json()}})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': result.model_dump_json()}}]})
    monkeypatch.setenv('API_KEY', 'test-only-placeholder-key')
    monkeypatch.setattr(ai_module, 'AIClient', lambda mode='mock', transport=None: actual_class(mode, transport or httpx.MockTransport(handler)))
    return captured

def inject_uploads(monkeypatch):
    class Upload(BytesIO):
        def __init__(self, path):
            super().__init__(path.read_bytes())
            self.name = path.name
    root = ROOT/'samples'
    def uploaded(label, **kwargs):
        if label.startswith('学生名单'): return Upload(root/'roster.csv')
        if label == '作业要求': return Upload(root/'requirements.txt')
        return [Upload(p) for p in sorted((root/'assignments').iterdir())]
    monkeypatch.setattr(st, 'file_uploader', uploaded)

def button(at, label):
    return next(b for b in at.button if b.label == label)

def check(at):
    assert not at.exception, [e.message for e in at.exception]

def test_old_running_process_refreshes_ai_client_without_losing_batch():
    import subprocess
    import sys
    code = '''
import os
os.environ.update({'TEAM_DEMO':'false','OLLAMA_ENABLED':'true','AI_MODE':'ollama','API_KEY':'test-placeholder',
                   'OLLAMA_BASE_URL':'http://127.0.0.1:11434','OLLAMA_MODEL':'coursework-qwen3:8b'})
from pathlib import Path
from streamlit.testing.v1 import AppTest
from core import ai_client
ai_client.AIClient.describe_local_model = lambda self: {'parameter_size':'8.2B','architecture':'qwen3','quantization':'Q4_K_M','model_context':131072,'context':8192}
at = AppTest.from_file(str(Path.cwd()/'app.py')).run()
next(b for b in at.button if b.label == '载入匿名样例（10 份，按当前模式分析）').click().run()
batch = at.session_state['batch']
batch.mode = 'ollama（本地模型，无需 Key）'
ai_client.CLIENT_VERSION = None
class OldClient:
    def __init__(self, *args, **kwargs):
        raise ValueError('未知运行模式')
ai_client.AIClient = OldClient
at.run()
assert not at.exception, [e.message for e in at.exception]
assert at.session_state['batch'] is batch
assert batch.mode == 'ollama'
assert len(batch.documents) == 10
assert ai_client.AIClient('ollama').mode == 'ollama'
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')

def test_three_page_review_and_download(monkeypatch):
    inject_uploads(monkeypatch)
    captured = []
    original = st.download_button
    def capture(*args, **kwargs):
        captured.append(kwargs['data'])
        return original(*args, **kwargs)
    monkeypatch.setattr(st, 'download_button', capture)
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    check(at)
    button(at, '读取上传并建立新批次').click().run()
    check(at)
    button(at, '阶段一：提取标准 / 重试').click().run()
    button(at, '确认此评价标准').click().run()
    check(at)
    at.sidebar.radio[0].set_value('个人分析与审核').run()
    button(at, '阶段二：分析所有未成功项').click().run()
    check(at)
    batch = at.session_state['batch']
    assert len(batch.results) == 10
    for sid in list(batch.selected):
        at.selectbox[0].set_value(sid).run()
        at.text_area[0].set_value('教师已修改：请增加异常输入验证。').run()
        button(at, '保存反馈并标记已审核').click().run()
        check(at)
    at.sidebar.radio[0].set_value('班级汇总与导出').run()
    button(at, '阶段三：仅发送统计生成讲评 / 重试').click().run()
    check(at)
    at.text_area[0].set_value('教师已审核讲评：集中讨论输入验证与证据。').run()
    button(at, '保存讲评并标记已审核').click().run()
    check(at)
    assert captured
    with ZipFile(BytesIO(captured[-1])) as z:
        assert '教师已修改' in z.read('feedback/2023001.txt').decode()
        assert '教师已审核讲评' in z.read('class_report.txt').decode()
    assert len(at.get('download_button')) == 1

def test_upload_route(monkeypatch):
    inject_uploads(monkeypatch)
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    button(at, '读取上传并建立新批次').click().run()
    check(at)
    assert len(at.session_state['batch'].selected) == 10

def test_standard_change_clears_old_review_widgets():
    import json
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    button(at, '载入匿名样例（10 份，按当前模式分析）').click().run()
    button(at, '阶段一：提取标准 / 重试').click().run()
    button(at, '确认此评价标准').click().run()
    at.sidebar.radio[0].set_value('个人分析与审核').run()
    button(at, '阶段二：分析所有未成功项').click().run()
    at.text_area[0].set_value('不应带入新标准的旧反馈').run()
    button(at, '保存反馈并标记已审核').click().run()
    at.sidebar.radio[0].set_value('上传与标准确认').run()
    criteria = json.loads(at.text_area[0].value)
    criteria['dimensions'][0]['name'] = '新标准目标'
    at.text_area[0].set_value(json.dumps(criteria, ensure_ascii=False)).run()
    button(at, '确认此评价标准').click().run()
    assert not at.session_state['batch'].results
    at.sidebar.radio[0].set_value('个人分析与审核').run()
    button(at, '阶段二：分析所有未成功项').click().run()
    check(at)
    assert '旧反馈' not in at.text_area[0].value

def test_ollama_page_uses_native_client(monkeypatch):
    import json
    import httpx
    import core.ai_client as ai_module
    from core.models import Document
    real_class = ai_module.AIClient
    mock_client = real_class()
    criteria = mock_client.extract_criteria('要求')
    calls = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        assert request.url.path == '/api/chat'
        payload = json.loads(json.loads(request.content)['messages'][1]['content'])
        calls.append(payload)
        if 'requirement' in payload:
            result = criteria
        elif 'paragraphs' in payload:
            doc = Document('x', 'x', paragraphs=[p['text'] for p in payload['paragraphs']])
            result = mock_client.analyze(doc, criteria, {})
        else:
            result = mock_client.class_outline(payload['statistics'], criteria)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': result.model_dump_json()}})
    monkeypatch.setattr(ai_module, 'AIClient', lambda mode: real_class(mode, httpx.MockTransport(handler)))
    at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    next(r for r in at.radio if r.label == '新批次模式').set_value('本地模型（Ollama）').run()
    button(at, '载入匿名样例（10 份，按当前模式分析）').click().run()
    assert at.session_state['batch'].mode == 'ollama'
    button(at, '阶段一：提取标准 / 重试').click().run()
    button(at, '确认此评价标准').click().run()
    at.sidebar.radio[0].set_value('个人分析与审核').run()
    button(at, '阶段二：分析所有未成功项').click().run()
    check(at)
    assert len(at.session_state['batch'].results) == 10
    at.sidebar.radio[0].set_value('班级汇总与导出').run()
    button(at, '阶段三：仅发送统计生成讲评 / 重试').click().run()
    check(at)
    assert len(calls) == 12
    assert set(calls[-1]) == {'statistics'}

def test_home_only_two_providers_and_real_model_details(fake_provider):
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    check(at)
    selector = next(r for r in at.radio if r.label == '新批次模式')
    assert selector.options == ['外部 API（DeepSeek）', '本地模型（Ollama）']
    assert not any('mock' in b.label.lower() for b in at.button)
    assert [m.value for m in at.metric] == ['8.2B', 'qwen3', 'Q4_K_M']
    assert 'coursework-qwen3:8b' in [c.value for c in at.code]
    parameters = at.dataframe[0].value
    assert '8192 tokens' in parameters['当前值'].tolist()
    assert '131072 tokens' in parameters['当前值'].tolist()
    assert not fake_provider, '仅查看配置不应触发模型推理'

def test_deepseek_ui_missing_key_and_independent_config(monkeypatch, fake_provider):
    monkeypatch.delenv('API_KEY')
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    next(r for r in at.radio if r.label == '新批次模式').set_value('外部 API（DeepSeek）').run()
    check(at)
    assert any('尚未配置 DeepSeek' in w.value for w in at.warning)
    assert any('deepseek-flash' in c.value for c in at.code)
    assert any('https://api.deepseek.com' in c.value for c in at.caption)
    assert not fake_provider

def test_deepseek_batch_selection_survives_import_and_calls_cloud(monkeypatch, fake_provider):
    monkeypatch.setenv('API_KEY', 'sensitive-test-key-not-for-display')
    inject_uploads(monkeypatch)
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    next(r for r in at.radio if r.label == '新批次模式').set_value('外部 API（DeepSeek）').run()
    button(at, '读取上传并建立新批次').click().run()
    assert at.session_state['batch'].mode == 'real'
    assert next(r for r in at.radio if r.label == '新批次模式').value == '外部 API（DeepSeek）'
    button(at, '阶段一：提取标准 / 重试').click().run()
    check(at)
    assert fake_provider[-1][0] == 'https://api.deepseek.com/chat/completions'
    for element_type in ('caption', 'code', 'markdown', 'success', 'info', 'warning', 'error'):
        assert all('sensitive-test-key-not-for-display' not in str(e.value) for e in at.get(element_type))

def test_local_metadata_unavailable_keeps_page_usable(monkeypatch):
    import core.ai_client as ai_module
    def unavailable(self):
        raise ai_module.AIError('暂未读取到本地模型元信息')
    # 此测试替换展示查询，不触碰推理结果。
    configured_client = ai_module.AIClient
    def factory(mode='ollama'):
        client = configured_client(mode)
        client.describe_local_model = lambda: unavailable(client)
        return client
    monkeypatch.setattr(ai_module, 'AIClient', factory)
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    check(at)
    assert any('暂未读取' in w.value for w in at.warning)
    assert len(next(r for r in at.radio if r.label == '新批次模式').options) == 2

def test_team_profile_ready_for_external_demo_local_disabled(monkeypatch, fake_provider):
    monkeypatch.setenv('TEAM_DEMO', 'true')
    monkeypatch.setenv('AI_MODE', 'real')
    monkeypatch.setenv('OLLAMA_ENABLED', 'false')
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    check(at)
    assert next(r for r in at.radio if r.label == '新批次模式').value == '外部 API（DeepSeek）'
    assert any('团队演示配置已就绪' in c.value for c in at.caption)
    next(r for r in at.radio if r.label == '新批次模式').set_value('本地模型（Ollama）').run()
    check(at)
    assert any('本地 AI 不可用' in e.value for e in at.error)
    assert button(at, '刷新本地模型信息').disabled
    assert button(at, '读取上传并建立新批次').disabled
    assert button(at, '载入匿名样例（10 份，按当前模式分析）').disabled
    assert not fake_provider


def test_team_profile_keeps_local_demo_enabled(monkeypatch, fake_provider):
    monkeypatch.setenv('TEAM_DEMO', 'true')
    monkeypatch.setenv('AI_MODE', 'real')
    monkeypatch.setenv('OLLAMA_ENABLED', 'true')
    at = AppTest.from_file(str(ROOT/'app.py')).run()
    next(r for r in at.radio if r.label == '新批次模式').set_value('本地模型（Ollama）').run()
    check(at)
    assert not any('本地 AI 不可用' in e.value for e in at.error)
    assert not button(at, '刷新本地模型信息').disabled
    assert not button(at, '载入匿名样例（10 份，按当前模式分析）').disabled
    button(at, '载入匿名样例（10 份，按当前模式分析）').click().run()
    assert at.session_state['batch'].mode == 'ollama'
    button(at, '阶段一：提取标准 / 重试').click().run()
    check(at)
    assert at.text_area[0].value
    assert fake_provider
