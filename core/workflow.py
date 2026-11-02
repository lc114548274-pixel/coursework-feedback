from .models import Batch, MAX_FILES, normalize_mode
from .parsing import parse_document
from .matching import read_roster, match_documents
from .rules import objective_checks
from .statistics import summarize

def create_batch(roster_bytes, requirement, submissions, mode='mock'):
    mode = normalize_mode(mode)
    if not 1 <= len(submissions) <= MAX_FILES:
        raise ValueError('每批需上传 1～15 份作业，推荐 10～15 份')
    roster = read_roster(roster_bytes)
    req = parse_document(requirement[0], requirement[1], 'requirement')
    if req.status != '正常':
        raise ValueError('作业要求无效：' + req.status + ' ' + req.error)
    docs = [parse_document(name, data, f'file_{i:02d}') for i, (name, data) in enumerate(submissions)]
    batch = Batch(roster, req, docs, mode=mode)
    groups, _ = match_documents(roster, docs)
    batch.selected = {sid: items[0].key for sid, items in groups.items() if len(items) == 1 and items[0].status == '正常'}
    return batch

def invalidate_report(batch):
    batch.outline = None
    batch.report = ''
    batch.report_reviewed = False

def confirm_criteria(batch, criteria):
    if batch.criteria != criteria:
        batch.results.clear()
        batch.errors.clear()
        batch.feedback.clear()
        batch.reviewed.clear()
        invalidate_report(batch)
    batch.criteria = criteria

def select_submission(batch, sid, key):
    groups, _ = match_documents(batch.roster, batch.documents)
    if key is not None and not any(d.key == key and d.status == '正常' for d in groups[sid]):
        raise ValueError('只能选择该学号的正常文件')
    if batch.selected.get(sid) != key:
        batch.selected.pop(sid, None)
        if key:
            batch.selected[sid] = key
        batch.results.pop(sid, None)
        batch.errors.pop(sid, None)
        batch.feedback.pop(sid, None)
        batch.reviewed.discard(sid)
        invalidate_report(batch)

def analyze_one(batch, sid, client):
    if not batch.criteria or client.mode != batch.mode:
        raise ValueError('标准未确认或模式不一致')
    doc = next(d for d in batch.documents if d.key == batch.selected[sid])
    # 重试前移除旧结果，以免失败后沿用旧统计。
    batch.results.pop(sid, None)
    batch.feedback.pop(sid, None)
    batch.reviewed.discard(sid)
    invalidate_report(batch)
    try:
        result = client.analyze(doc, batch.criteria, batch.roster)
        batch.results[sid] = result
        batch.feedback[sid] = result.feedback
        batch.errors.pop(sid, None)
        return True
    except Exception as exc:
        from .ai_client import AIError
        batch.errors[sid] = str(exc) if isinstance(exc, AIError) else '本份分析失败，请单项重试'
        return False

def batch_summary(batch):
    return summarize(batch.criteria, batch.results, len(batch.roster))
