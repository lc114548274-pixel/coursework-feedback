import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import httpx
import pytest
from core.models import Document, Criteria, MAX_TEXT, MAX_BYTES
from core.matching import read_roster, match_documents, student_id
from core.parsing import parse_document
from core.rules import objective_checks
from core.statistics import summarize
from core.ai_client import AIClient, AIError, validate_response
from core.workflow import create_batch, confirm_criteria, analyze_one, select_submission, batch_summary
from core.exporting import build_zip

ROOT = Path(__file__).resolve().parents[1] / 'samples'

@pytest.fixture
def batch():
    return create_batch((ROOT/'roster.csv').read_bytes(), ('requirements.txt', (ROOT/'requirements.txt').read_bytes()),
                        [(p.name, p.read_bytes()) for p in sorted((ROOT/'assignments').iterdir())])

@pytest.fixture
def criteria():
    return AIClient().extract_criteria('演示要求')

@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig'])
def test_roster_preserves_leading_zero(encoding):
    assert read_roster('student_id,name\n001,匿名甲\n'.encode(encoding)) == {'001': '匿名甲'}

@pytest.mark.parametrize('text', ['student_id,name\n001,A\n001,B\n', 'id,name\n1,A',
                                 'student_id,name\n1,', 'student_id,name\n1,A,extra'])
def test_invalid_roster(text):
    with pytest.raises(ValueError):
        read_roster(text.encode())

def test_exact_matching_and_all_statuses(batch):
    edges = ROOT/'edge_cases'
    batch.roster = read_roster((edges/'roster_missing.csv').read_bytes())
    batch.documents += [parse_document(p.name, p.read_bytes(), 'edge_'+str(i))
                        for i, p in enumerate(sorted(edges.iterdir())) if p.suffix != '.csv']
    groups, rows = match_documents(batch.roster, batch.documents)
    assert len(groups['2023001']) == 2
    assert any(r['匹配'] == '缺交' and r['学号'] == '2023011' for r in rows)
    assert any(r['匹配'] == '名单外文件' for r in rows)
    assert any('空文件' in r['解析'] for r in rows)
    assert any('扫描件' in r['解析'] for r in rows)
    assert any('解析失败' in r['解析'] for r in rows)
    assert student_id('20230010_report.txt') != '2023001'
    assert student_id('2023001张同学.txt') != '2023001'

def test_parse_formats_and_limits(batch):
    assert len(batch.documents) == 10
    assert all(d.status == '正常' and d.paragraphs for d in batch.documents)
    assert {Path(d.filename).suffix for d in batch.documents} == {'.txt', '.docx', '.pdf'}
    assert parse_document('x.txt', b'x'*(MAX_TEXT+1), '1').status == '解析失败'
    assert '5 MiB' in parse_document('x.txt', b'x'*(MAX_BYTES+1), '1').error
    assert parse_document('x.txt', b' \n\t', '1').status == '空文件'
    assert parse_document('x.txt', b'\xff', '1').status == '解析失败'
    assert parse_document('x.exe', b'abc', '1').status == '解析失败'

def test_rules_show_evidence(criteria):
    doc = parse_document('x.txt', '一、任务目标\n正文提到方法实现\n结果反思\n a b '.encode(), '1')
    checks = objective_checks(doc, criteria)
    assert checks['必需章节'][0]['段落编号'] == [1]
    assert not checks['必需章节'][1]['存在']
    assert checks['必需章节'][2]['段落编号'] == [3]
    assert checks['非空白字符数'] == len('一、任务目标正文提到方法实现结果反思ab')

def test_statistics_denominator_dedup(criteria):
    result = AIClient().analyze(Document('1', 'x', paragraphs=['任务目标']), criteria, {})
    result.findings[0].status = '完成'
    result.findings[0].problems = ['同一问题', '同一问题']
    summary = summarize(criteria, {'a': result, 'b': result}, 3)
    assert summary['dimensions'][0]['完成比例'] == 1
    assert summary['dimensions'][0]['常见问题'] == [{'问题': '同一问题', '人数': 2}]
    assert summary['未纳入统计人数'] == 1
    assert summarize(criteria, {}, 10)['dimensions'][0]['完成比例'] is None

@pytest.mark.parametrize('mutation', ['missing', 'bad_id', 'duplicate', 'bad_reference', 'no_evidence', 'bad_status', 'extra', 'bool_reference'])
def test_analysis_validation(criteria, mutation):
    value = AIClient().analyze(Document('1', 'x', paragraphs=['任务目标']), criteria, {}).model_dump()
    if mutation == 'missing': del value['feedback']
    elif mutation == 'bad_id': value['findings'][0]['dimension_id'] = 'D9'
    elif mutation == 'duplicate': value['findings'][1]['dimension_id'] = 'D1'
    elif mutation == 'bad_reference': value['findings'][0]['paragraph_ids'] = [2]
    elif mutation == 'no_evidence': value['findings'][0]['paragraph_ids'] = []
    elif mutation == 'bad_status': value['findings'][0]['status'] = '优秀'
    elif mutation == 'extra': value['score'] = 100
    elif mutation == 'bool_reference': value['findings'][0]['paragraph_ids'] = [True]
    with pytest.raises(AIError):
        validate_response('analysis', json.dumps(value), criteria, 1)

@pytest.mark.parametrize('raw', ['', 'not json', '{}', '```json\n{}\n```'])
def test_bad_ai_json(criteria, raw):
    with pytest.raises(AIError): validate_response('analysis', raw, criteria, 1)

def test_criteria_and_outline_validation(criteria):
    data = criteria.model_dump()
    data['dimensions'][1]['id'] = 'D1'
    with pytest.raises(AIError): validate_response('criteria', json.dumps(data))
    with pytest.raises(AIError):
        validate_response('outline', json.dumps({'summary': '摘要', 'outline': ['提纲'], 'dimension_ids': ['D9']}), criteria)

@pytest.mark.parametrize('case', ['timeout', 'http', 'empty', 'invalid_json', 'missing', 'truncated'])
def test_transport_failures(monkeypatch, criteria, case):
    monkeypatch.setenv('API_KEY', 'test-placeholder')
    def handler(request):
        if case == 'timeout': raise httpx.ReadTimeout('timeout')
        if case == 'http': return httpx.Response(429)
        if case == 'missing': return httpx.Response(200, json={})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length' if case == 'truncated' else 'stop',
                    'message': {'content': '' if case == 'empty' else 'not json'}}]})
    with pytest.raises(AIError):
        AIClient('real', httpx.MockTransport(handler)).extract_criteria('要求')

def test_real_payload_privacy_and_summary_only(monkeypatch, criteria):
    monkeypatch.setenv('API_KEY', 'test-placeholder')
    captured = []
    result = AIClient().analyze(Document('1', 'x', paragraphs=['任务目标']), criteria, {})
    outline = AIClient().class_outline(summarize(criteria, {}, 0), criteria)
    def handler(request):
        data = json.loads(request.content)
        captured.append(json.loads(data['messages'][1]['content']))
        response = result if 'paragraphs' in captured[-1] else outline
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': response.model_dump_json()}}]})
    client = AIClient('real', httpx.MockTransport(handler))
    client.analyze(Document('x', '2023001_匿名甲.txt', paragraphs=['任务目标 匿名甲 2023001']), criteria, {'2023001': '匿名甲'})
    assert '2023001' not in json.dumps(captured[0]) and '匿名甲' not in json.dumps(captured[0], ensure_ascii=False)
    client.class_outline(summarize(criteria, {'x': result}, 1), criteria)
    assert set(captured[1]) == {'statistics'}

def test_complete_mock_flow_in_memory(batch, criteria, monkeypatch):
    confirm_criteria(batch, criteria)
    # 应用业务流禁止文件写入。测试也不把模拟上传及 ZIP 落盘。
    import builtins
    original = builtins.open
    def guarded(file, mode='r', *args, **kwargs):
        assert not any(c in mode for c in 'wax+'), '运行流程发生文件写入'
        return original(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    for sid in batch.selected:
        assert analyze_one(batch, sid, AIClient())
        batch.feedback[sid] = '教师审核修改后的反馈：请补充边界测试。'
        batch.reviewed.add(sid)
    summary = batch_summary(batch)
    batch.outline = AIClient().class_outline(summary, criteria)
    batch.report = batch.outline.summary + '\n教师审核后的讲评'
    batch.report_reviewed = True
    data = build_zip(batch)
    with ZipFile(BytesIO(data)) as z:
        assert len([n for n in z.namelist() if n.startswith('feedback/')]) == 10
        assert '教师审核修改后的反馈' in z.read('feedback/2023001.txt').decode()
        assert json.loads(z.read('statistics.json'))['成功分析人数'] == 10
        assert 'processing.csv' in z.namelist()

def test_single_failure_retry_and_invalidation(batch, criteria):
    confirm_criteria(batch, criteria)
    class Failing(AIClient):
        def analyze(self, *args): raise AIError('测试错误')
    ids = list(batch.selected)
    assert not analyze_one(batch, ids[0], Failing())
    assert analyze_one(batch, ids[1], AIClient())
    assert analyze_one(batch, ids[0], AIClient())
    assert not batch.errors
    batch.reviewed.add(ids[0])
    batch.report = '旧报告'
    batch.report_reviewed = True
    select_submission(batch, ids[0], None)
    assert ids[0] not in batch.results and not batch.report
    updated = criteria.model_copy(deep=True)
    updated.dimensions[0].name = '修改后的维度'
    confirm_criteria(batch, updated)
    assert not batch.results and not batch.reviewed
    with pytest.raises(ValueError): build_zip(batch)

def test_batch_limits(batch):
    with pytest.raises(ValueError): create_batch(b'', ('a.txt', b'a'), [('a.txt', b'a')]*16)

@pytest.mark.parametrize('mode', ['ollama', 'Ollama', ' ollama ', 'ollama（本地模型，无需 Key）'])
def test_mode_labels_normalized_at_boundary(mode):
    from core.models import normalize_mode
    assert normalize_mode(mode) == 'ollama'
    assert AIClient(mode).mode == 'ollama'
    batch = create_batch(b'student_id,name\n001,A\n', ('req.txt', b'requirement'), [('001.txt', b'work')], mode=mode)
    assert batch.mode == 'ollama'

def test_invalid_mode_not_silently_downgraded():
    with pytest.raises(AIError): AIClient('unknown')

def test_duplicate_selection_is_explicit(criteria):
    req = ('req.txt', b'requirement')
    batch = create_batch(b'student_id,name\n001,A\n', req,
                         [('001_first.txt', b'first'), ('001_second.txt', b'second'), ('001_empty.txt', b'')])
    assert not batch.selected
    confirm_criteria(batch, criteria)
    with pytest.raises(ValueError): select_submission(batch, '001', 'file_02')
    select_submission(batch, '001', 'file_00')
    assert analyze_one(batch, '001', AIClient())
    batch.reviewed.add('001')
    select_submission(batch, '001', 'file_01')
    assert not batch.results and not batch.reviewed
    assert analyze_one(batch, '001', AIClient())

def test_real_requires_env_key(monkeypatch):
    monkeypatch.delenv('API_KEY', raising=False)
    with pytest.raises(AIError, match='API_KEY'): AIClient('real')
    assert AIClient().mode == 'mock'

@pytest.mark.parametrize('field', ['feedback', 'paragraph_ids'])
def test_ai_whitespace_and_invalid_content_type(criteria, field):
    result = AIClient().analyze(Document('1', 'x', paragraphs=['任务目标']), criteria, {}).model_dump()
    if field == 'feedback': result[field] = '  '
    else: result['findings'][0][field] = [0]
    with pytest.raises(AIError): validate_response('analysis', json.dumps(result), criteria, 1)
    with pytest.raises(AIError): validate_response('analysis', {'not': 'text'}, criteria, 1)
