"""显式调用 DeepSeek 测试真实页面，仅用仓库匿名数据；不输出密钥或保存反馈。"""
import json
import os
import sys
import time
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from dotenv import load_dotenv
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.ai_client import AIClient

def button(at, label):
    return next(b for b in at.button if b.label == label)

def check(at):
    assert not at.exception, '页面出现异常'

def main():
    load_dotenv(ROOT/'.env')
    if not os.getenv('API_KEY'):
        raise SystemExit('API_KEY 尚未配置')
    os.environ['AI_MODE'] = 'real'
    os.environ['TEAM_DEMO'] = 'true'
    os.environ['OLLAMA_ENABLED'] = 'false'
    captured, calls = [], []
    download = st.download_button
    request = AIClient._request
    def capture(*args, **kwargs):
        captured.append(kwargs['data'])
        return download(*args, **kwargs)
    def measured(client, stage, *args, **kwargs):
        result = request(client, stage, *args, **kwargs)
        calls.append({'stage': stage, **client.last_metrics})
        return result
    started = time.perf_counter()
    with patch('streamlit.download_button', capture), patch.object(AIClient, '_request', measured):
        at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=240).run()
        check(at)
        selector = next(r for r in at.radio if r.label == '新批次模式')
        assert selector.value == '外部 API（DeepSeek）'
        selector.set_value('本地模型（Ollama）').run()
        assert any('本地 AI 不可用' in e.value for e in at.error)
        assert button(at, '载入匿名样例（10 份，按当前模式分析）').disabled
        next(r for r in at.radio if r.label == '新批次模式').set_value('外部 API（DeepSeek）').run()
        button(at, '载入匿名样例（10 份，按当前模式分析）').click().run()
        button(at, '阶段一：提取标准 / 重试').click().run()
        check(at)
        assert at.text_area[0].value, 'DeepSeek 标准提取失败'
        standard = json.loads(at.text_area[0].value)
        standard['required_sections'] = ['任务目标', '方法实现', '结果反思']
        at.text_area[0].set_value(json.dumps(standard, ensure_ascii=False)).run()
        button(at, '确认此评价标准').click().run()
        print('DeepSeek stage1 OK; teacher standard edit simulated', flush=True)
        at.sidebar.radio[0].set_value('个人分析与审核').run()
        button(at, '阶段二：分析所有未成功项').click().run()
        check(at)
        batch = at.session_state['batch']
        assert batch.mode == 'real' and len(batch.results) == 10, batch.errors
        print('DeepSeek stage2 OK 10/10', flush=True)
        for sid in batch.selected:
            at.selectbox[0].set_value(sid).run()
            at.text_area[0].set_value(at.text_area[0].value + '\n【集成测试模拟教师修改】请核对实验依据。').run()
            button(at, '保存反馈并标记已审核').click().run()
        at.sidebar.radio[0].set_value('班级汇总与导出').run()
        button(at, '阶段三：仅发送统计生成讲评 / 重试').click().run()
        check(at)
        assert at.text_area[0].value, 'DeepSeek 班级讲评生成失败'
        at.text_area[0].set_value(at.text_area[0].value + '\n【集成测试模拟讲评审核】').run()
        button(at, '保存讲评并标记已审核').click().run()
        check(at)
        assert captured
        with ZipFile(BytesIO(captured[-1])) as archive:
            assert archive.testzip() is None
            assert len([n for n in archive.namelist() if n.startswith('feedback/')]) == 10
            assert '集成测试模拟教师修改' in archive.read('feedback/2023001.txt').decode()
        for kind in ('caption', 'code', 'markdown', 'info', 'success', 'error'):
            assert all(os.environ['API_KEY'] not in str(node.value) for node in at.get(kind))
        usage = {key: sum(c.get(key) or 0 for c in calls) for key in ('prompt_tokens','completion_tokens','total_tokens')}
        print(f'DeepSeek stage3/export OK requests={len(calls)} usage={usage} ZIP_bytes={len(captured[-1])} seconds={time.perf_counter()-started:.1f}', flush=True)

if __name__ == '__main__':
    main()
