"""显式运行本机真实推理，仅使用仓库匿名样例；所有结果、ZIP 保留在内存。"""
import argparse
import json
import os
import sys
import time
import httpx
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.ai_client import AIClient, anonymize
from core.models import Criteria
from core.workflow import create_batch, confirm_criteria, analyze_one, batch_summary
from core.exporting import build_zip

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='coursework-qwen3:8b')
    parser.add_argument('--limit', type=int, default=10, choices=range(1, 11))
    parser.add_argument('--debug', action='store_true', help='仅为仓库匿名样例打印本地服务错误')
    args = parser.parse_args()
    os.environ['OLLAMA_BASE_URL'] = 'http://127.0.0.1:11434'
    os.environ['OLLAMA_MODEL'] = args.model
    os.environ.setdefault('OLLAMA_TIMEOUT', '180')
    samples = ROOT/'samples'
    files = sorted((samples/'assignments').iterdir())[:args.limit]
    batch = create_batch((samples/'roster.csv').read_bytes(),
                         ('requirements.txt', (samples/'requirements.txt').read_bytes()),
                         [(p.name, p.read_bytes()) for p in files], mode='ollama')
    def debug_request(request):
        if request.url.path == '/api/chat':
            request_body = json.loads(request.content)
            request_body['stream'] = True
            content, thinking, final = '', '', {}
            with httpx.stream('POST', str(request.url), json=request_body, timeout=180, trust_env=False) as streamed:
                if streamed.status_code >= 400:
                    streamed.read()
                    print('DEBUG HTTP ' + str(streamed.status_code) + ' ' + streamed.text[:2000], flush=True)
                    return httpx.Response(streamed.status_code, content=streamed.content)
                for line in streamed.iter_lines():
                    part = json.loads(line)
                    content += part.get('message', {}).get('content', '')
                    thinking += part.get('message', {}).get('thinking', '')
                    if len(content) < 500 and part.get('message', {}).get('content'):
                        print('DEBUG token=' + json.dumps(part['message']['content'], ensure_ascii=True), flush=True)
                    if part.get('done'):
                        final = part
            final['message'] = {'content': content, 'thinking': thinking}
            response = httpx.Response(200, json=final)
        else:
            response = httpx.post(str(request.url), content=request.content, headers=request.headers, timeout=180, trust_env=False)
        if response.status_code >= 400:
            print('DEBUG HTTP ' + str(response.status_code) + ' ' + response.text[:2000], flush=True)
        if request.url.path == '/api/chat' and response.status_code == 200:
            body = response.json()
            if body.get('done_reason') != 'stop':
                print('DEBUG unfinished=' + json.dumps(body, ensure_ascii=True)[:2500], flush=True)
        return response
    client = AIClient('ollama', httpx.MockTransport(debug_request) if args.debug else None)
    started = time.perf_counter()
    print('LIVE model=' + args.model, flush=True)
    criteria = client.extract_criteria(anonymize(batch.requirement.text, batch.roster))
    print('stage1 OK dimensions=' + str(len(criteria.dimensions)) + ' elapsed=' + str(round(time.perf_counter()-started, 1)) + ' metrics=' + str(client.last_metrics), flush=True)
    # 样例只在终端展示标准摘要，不写入本地报告。
    print('criteria=' + json.dumps(criteria.model_dump(), ensure_ascii=True), flush=True)
    # 显式模拟教师修改、确认样例标准，不将手改内容冒充模型输出。
    criteria = Criteria(dimensions=[
        {'id': 'D1', 'name': '任务目标', 'checkpoints': ['说明背景、目标和输入输出']},
        {'id': 'D2', 'name': '方法实现', 'checkpoints': ['说明解析、校验及错误处理步骤和依据']},
        {'id': 'D3', 'name': '结果反思', 'checkpoints': ['提供测试结果，说明限制及改进方向']}],
        required_sections=['任务目标', '方法实现', '结果反思'])
    confirm_criteria(batch, criteria)
    print('TEACHER SIMULATION: rubric edited and confirmed against sample requirement', flush=True)
    for sid in batch.selected:
        tick = time.perf_counter()
        ok = analyze_one(batch, sid, client)
        print(f'stage2 {sid} {"OK" if ok else "FAILED"} seconds={time.perf_counter()-tick:.1f} ' + batch.errors.get(sid, '') + ' metrics=' + str(client.last_metrics) + ' correction_retries=' + str(client.last_retries), flush=True)
        if ok:
            # 集成测试模拟教师保存动作，不将其称为真实教师审核。
            batch.feedback[sid] += '\n【集成测试模拟审核修改】请核对并补充测试证据。'
            batch.reviewed.add(sid)
    if batch.errors:
        print('FAILED ITEMS ' + json.dumps(batch.errors, ensure_ascii=False), flush=True)
        return 1
    summary = batch_summary(batch)
    print('stage2 summary=' + str(summary['成功分析人数']), flush=True)
    batch.outline = client.class_outline(summary, criteria)
    print('stage3 OK outline_items=' + str(len(batch.outline.outline)), flush=True)
    batch.report = batch.outline.summary + '\n' + '\n'.join(batch.outline.outline) + '\n【集成测试模拟审核】'
    batch.report_reviewed = True
    exported = build_zip(batch)
    with ZipFile(BytesIO(exported)) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.startswith('feedback/')]) == len(files)
        assert '集成测试模拟审核修改' in archive.read('feedback/' + next(iter(batch.selected)) + '.txt').decode()
    print(f'EXPORT OK bytes={len(exported)} total_seconds={time.perf_counter()-started:.1f}', flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
