import json
import httpx
import pytest
from core.ai_client import AIClient, AIError
from core.models import Document
from core.statistics import summarize

@pytest.fixture(autouse=True)
def local_environment(monkeypatch):
    for name in ['API_BASE_URL', 'API_MODEL', 'AI_MODEL', 'AI_TIMEOUT', 'API_KEY', 'OLLAMA_NUM_CTX', 'OLLAMA_MAX_TOKENS']:
        monkeypatch.delenv(name, raising=False)

def test_native_three_stages_no_key_and_exact_schema():
    mock = AIClient()
    criteria = mock.extract_criteria('要求')
    doc = Document('x', '001_作业.txt', paragraphs=['任务目标 匿名甲 001', '方法实现', '结果反思'])
    analysis = mock.analyze(doc, criteria, {})
    summary = summarize(criteria, {'local': analysis}, 1)
    outline = mock.class_outline(summary, criteria)
    captured = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        assert 'authorization' not in request.headers
        body = json.loads(request.content)
        captured.append(body)
        assert body['stream'] is False and body['think'] is False
        assert body['options']['temperature'] == 0
        assert isinstance(body['format'], dict)
        payload = json.loads(body['messages'][1]['content'])
        result = criteria if 'requirement' in payload else analysis if 'paragraphs' in payload else outline
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {
            'thinking': '这不是最终 JSON，不能混进结果', 'content': result.model_dump_json()}})
    client = AIClient('ollama', httpx.MockTransport(handler))
    assert client.extract_criteria('要求') == criteria
    assert client.analyze(doc, criteria, {'001': '匿名甲'}) == analysis
    assert client.class_outline(summary, criteria) == outline
    assert '匿名甲' not in json.dumps(captured[1], ensure_ascii=False)
    assert '001' not in captured[1]['messages'][1]['content']
    assert set(json.loads(captured[2]['messages'][1]['content'])) == {'statistics'}
    finding = captured[1]['format']['$defs']['Finding']['oneOf'][0]['properties']
    assert finding['dimension_id']['enum'] == ['D1', 'D2', 'D3']
    assert finding['paragraph_ids']['items']['maximum'] == 3
    assert finding['paragraph_ids']['minItems'] == 1

@pytest.mark.parametrize('address', ['http://example.com:11434', 'https://example.com',
    'http://localhost.evil.test', 'http://127.0.0.1@evil.test', 'http://localhost/api/chat',
    'file:///tmp/test', 'http://localhost?key=value', 'http://localhost/#fragment'])
def test_only_local_ollama_addresses(monkeypatch, address):
    monkeypatch.setenv('OLLAMA_BASE_URL', address)
    with pytest.raises(AIError): AIClient('ollama')

@pytest.mark.parametrize('address', ['http://localhost:11434/v1/', 'http://127.0.0.1:11434', 'http://[::1]:11434'])
def test_local_addresses_accept_no_key(monkeypatch, address):
    monkeypatch.setenv('OLLAMA_BASE_URL', address)
    assert not AIClient('ollama').base.endswith('/v1')

@pytest.mark.parametrize('case', ['timeout', 'offline', 'not_found', 'server_error', 'truncated', 'empty', 'invalid', 'missing', 'wrong_type'])
def test_native_errors(case):
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        if case == 'timeout': raise httpx.ReadTimeout('timeout')
        if case == 'offline': raise httpx.ConnectError('offline')
        if case == 'not_found': return httpx.Response(404)
        if case == 'server_error': return httpx.Response(500)
        if case == 'missing': return httpx.Response(200, json={})
        if case == 'wrong_type': return httpx.Response(200, json=[])
        return httpx.Response(200, json={'done': True, 'done_reason': 'length' if case == 'truncated' else 'stop',
            'message': {'content': '' if case == 'empty' else 'not json'}})
    with pytest.raises(AIError):
        AIClient('ollama', httpx.MockTransport(handler)).extract_criteria('要求')

def test_context_overflow_rejected_before_network():
    def handler(request):
        pytest.fail('上下文超限不得发送或截断')
    with pytest.raises(AIError, match='不会截断'):
        AIClient('ollama', httpx.MockTransport(handler)).extract_criteria('长文本'*10000)

@pytest.mark.parametrize('variable,value', [('OLLAMA_TIMEOUT', 'nan'), ('OLLAMA_TIMEOUT','601'),
    ('OLLAMA_NUM_CTX','bad'), ('OLLAMA_NUM_CTX','1024'), ('OLLAMA_MAX_TOKENS','20000')])
def test_local_configuration_validation(monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    with pytest.raises(AIError): AIClient('ollama')

def test_remote_still_requires_https_and_key(monkeypatch):
    with pytest.raises(AIError, match='API_KEY'): AIClient('real')
    monkeypatch.setenv('API_KEY', 'test-placeholder')
    monkeypatch.setenv('API_BASE_URL', 'http://127.0.0.1:11434')
    with pytest.raises(AIError, match='HTTPS'): AIClient('real')

def test_model_context_limit_respected_even_if_configuration_larger(monkeypatch):
    monkeypatch.setenv('OLLAMA_NUM_CTX', '32768')
    calls = []
    def handler(request):
        calls.append(request.url.path)
        assert request.url.path == '/api/show'
        return httpx.Response(200, json={'model_info': {'gemma.context_length': 4096}})
    with pytest.raises(AIError, match='实际上下文仅 4096'):
        AIClient('ollama', httpx.MockTransport(handler)).extract_criteria('要求'*600)
    assert calls == ['/api/show']

def test_invalid_result_gets_one_targeted_correction():
    mock = AIClient()
    criteria = mock.extract_criteria('要求')
    result = mock.analyze(Document('x', 'x', paragraphs=['任务目标']), criteria, {})
    bad = result.model_dump()
    bad['findings'][0]['paragraph_ids'] = []
    requests = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        body = json.loads(request.content)
        requests.append(body)
        raw = json.dumps(bad, ensure_ascii=False) if len(requests) == 1 else result.model_dump_json()
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': raw}})
    client = AIClient('ollama', httpx.MockTransport(handler))
    assert client.analyze(Document('x', 'x', paragraphs=['任务目标']), criteria, {}) == result
    assert client.last_retries == 1 and len(requests) == 2
    assert 'D1' in requests[1]['messages'][-1]['content']
    assert '段落依据' in requests[1]['messages'][-1]['content']

def test_invalid_result_correction_does_not_loop():
    calls = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        calls.append(1)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': '{}'}})
    with pytest.raises(AIError, match='一次纠错后仍未通过校验'):
        AIClient('ollama', httpx.MockTransport(handler)).extract_criteria('要求')
    assert len(calls) == 2

def test_required_section_candidates_grounded_in_source():
    criteria = AIClient().extract_criteria('要求')
    captured = []
    def handler(request):
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'model_info': {'gemma.context_length': 8192}})
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': criteria.model_dump_json()}})
    AIClient('ollama', httpx.MockTransport(handler)).extract_criteria('请完成一个 Python 文件分析实验。\n任务目标\n说明背景。\n方法实现\n说明步骤。\n结果反思\n说明限制。')
    assert captured[0]['format']['properties']['required_sections']['items']['enum'] == ['任务目标', '方法实现', '结果反思']
    assert 'heading_candidates' in json.loads(captured[0]['messages'][1]['content'])

@pytest.mark.parametrize('address', ['http://localhost:abc', 'http://[::1'])
def test_invalid_local_port_or_address_has_friendly_error(monkeypatch, address):
    monkeypatch.setenv('OLLAMA_BASE_URL', address)
    with pytest.raises(AIError, match='地址或端口无效'): AIClient('ollama')
