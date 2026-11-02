"""显式测试真实 Streamlit 三页 + 本机 Ollama，只使用匿名样例，ZIP 不落盘。"""
import json
import sys
import time
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def button(at, label):
    return next(b for b in at.button if b.label == label)

def check(at):
    assert not at.exception, [e.message for e in at.exception]

def main():
    captured = []
    original = st.download_button
    def capture(*args, **kwargs):
        captured.append(kwargs['data'])
        return original(*args, **kwargs)
    started = time.perf_counter()
    with patch('streamlit.download_button', capture):
        at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=240).run()
        check(at)
        next(r for r in at.radio if r.label == '新批次模式').set_value('本地模型（Ollama）').run()
        button(at, '载入匿名样例（10 份，按当前模式分析）').click().run()
        button(at, '阶段一：提取标准 / 重试').click().run()
        check(at)
        assert at.text_area[0].value, '真实标准提取失败'
        criteria = json.loads(at.text_area[0].value)
        criteria['required_sections'] = ['任务目标', '方法实现', '结果反思']
        at.text_area[0].set_value(json.dumps(criteria, ensure_ascii=False)).run()
        button(at, '确认此评价标准').click().run()
        print('UI stage1 OK; teacher standard edit simulated', flush=True)
        at.sidebar.radio[0].set_value('个人分析与审核').run()
        button(at, '阶段二：分析所有未成功项').click().run()
        check(at)
        batch = at.session_state['batch']
        assert batch.mode == 'ollama' and len(batch.results) == 10, batch.errors
        print('UI stage2 OK 10/10 real local analysis', flush=True)
        for sid in batch.selected:
            at.selectbox[0].set_value(sid).run()
            at.text_area[0].set_value(at.text_area[0].value + '\n【UI 集成测试模拟教师修改】请核对实验依据。').run()
            button(at, '保存反馈并标记已审核').click().run()
            check(at)
        at.sidebar.radio[0].set_value('班级汇总与导出').run()
        button(at, '阶段三：仅发送统计生成讲评 / 重试').click().run()
        check(at)
        assert at.text_area[0].value, '真实班级讲评生成失败'
        at.text_area[0].set_value(at.text_area[0].value + '\n【UI 集成测试模拟教师讲评审核】').run()
        button(at, '保存讲评并标记已审核').click().run()
        check(at)
        assert captured and len(at.get('download_button')) == 1
        with ZipFile(BytesIO(captured[-1])) as archive:
            assert archive.testzip() is None
            assert len([n for n in archive.namelist() if n.startswith('feedback/')]) == 10
            assert 'UI 集成测试模拟教师修改' in archive.read('feedback/2023001.txt').decode()
        print(f'UI stage3/download OK ZIP bytes={len(captured[-1])} total_seconds={time.perf_counter()-started:.1f}', flush=True)

if __name__ == '__main__':
    main()
