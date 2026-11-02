"""课程作业多维分析与智能反馈系统：仅会话内存，无数据库或持久缓存。"""
import json
import os
import importlib
from pathlib import Path
from uuid import uuid4
import streamlit as st
from dotenv import load_dotenv
from core import models as models_module
if getattr(models_module, 'MODELS_VERSION', None) != '2026-11-02-two-providers':
    importlib.reload(models_module)
from core.models import Criteria, MODE_LABELS, normalize_mode
from core import config as config_module
if getattr(config_module, 'CONFIG_VERSION', None) != '2026-11-02-team-demo':
    importlib.reload(config_module)
from core import ai_client as ai_client_module
# 已打开的 Streamlit 进程可能仍持有新增 Ollama 支持前的模块。
# 只在版本不符时重载业务模块，不重启服务，也不清除教师的会话数据。
if getattr(ai_client_module, 'CLIENT_VERSION', None) != '2026-11-02-team-demo':
    importlib.reload(ai_client_module)
from core.ai_client import AIClient, AIError, anonymize
from core.matching import match_documents
from core.rules import objective_checks
from core.workflow import create_batch, confirm_criteria, select_submission, analyze_one, batch_summary
from core.exporting import build_zip
from core.config import ProviderConfig, migrate_legacy_local_environment, local_inference_enabled

if not os.environ.get('API_KEY'):
    os.environ.pop('API_KEY', None)
load_dotenv(Path(__file__).parent / '.env', override=False)
if os.getenv('TEAM_DEMO', '').lower() == 'true':
    # 团队包明确使用随包环境配置，避免同学电脑已有变量意外覆盖演示参数。
    load_dotenv(Path(__file__).parent / '.env', override=True)
migrate_legacy_local_environment()
st.set_page_config(page_title='课程作业多维分析与智能反馈系统', layout='wide')
st.title('课程作业多维分析与智能反馈系统')
st.caption('辅助分析 → 教师审核；不自动给出成绩。上传与结果仅在当前会话内存处理，主动下载才生成保存文件。')

def install_batch(batch):
    # 清掉旧批次的文本编辑器及上传控件引用。
    for key in list(st.session_state):
        if key not in ('page', 'new_batch_mode'):
            del st.session_state[key]
    st.session_state.batch = batch
    st.session_state.token = uuid4().hex

if st.sidebar.button('清空本次会话'):
    st.session_state.clear()
    st.rerun()
page = st.sidebar.radio('页面', ['上传与标准确认', '个人分析与审核', '班级汇总与导出'], key='page')
batch = st.session_state.get('batch')
if batch:
    try:
        batch.mode = normalize_mode(batch.mode)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    if batch.mode == 'mock':
        st.warning('这是旧版演示批次，已保留数据供查看。请建立外部 API 或本地模型批次继续分析。')
    elif batch.mode == 'ollama':
        st.info('本地 Ollama 模式：去标识化文本只发往本机模型，分析结论仍须教师审核。')
    else:
        st.info('DeepSeek 外部 API 模式：将发送去标识化文本至配置的接口；正文中的其他个人信息请先自行移除。')

if page == '上传与标准确认':
    modes = list(MODE_LABELS.values())
    default_mode = {'real': 0, 'ollama': 1}.get(os.getenv('AI_MODE', 'ollama'), 1)
    if st.session_state.get('new_batch_mode') not in (None, *modes):
        del st.session_state['new_batch_mode']
    mode_label = st.radio('新批次模式', modes, index=default_mode, horizontal=True, key='new_batch_mode')
    mode = normalize_mode(mode_label)
    new_batch_unavailable = False
    try:
        config = ProviderConfig.from_environment(mode)
        new_batch_unavailable = not config.enabled
        with st.container(border=True):
            if mode == 'ollama':
                st.subheader('本地模型配置')
                st.caption('通过本机 Ollama 运行，不需要 API Key。模型信息读取自本机服务，推理参数与实际请求保持一致。')
                st.write('模型名称：')
                st.code(config.model, language=None)
                st.caption('服务地址：' + config.base_url)
                refresh = st.button('刷新本地模型信息', disabled=not config.enabled)
                fingerprint = (config.base_url, config.model, config.num_ctx, config.enabled)
                cached = st.session_state.get('_local_model_metadata', {})
                if not config.enabled:
                    cached = {'fingerprint': fingerprint, 'error': '团队演示包未提供本地模型，请使用 DeepSeek 外部 API。'}
                    st.error('本地 AI 不可用：团队演示配置已关闭本地推理。')
                elif refresh or cached.get('fingerprint') != fingerprint:
                    try:
                        cached = {'fingerprint': fingerprint, 'data': AIClient('ollama').describe_local_model()}
                    except AIError as exc:
                        cached = {'fingerprint': fingerprint, 'error': str(exc)}
                    st.session_state['_local_model_metadata'] = cached
                info = cached.get('data', {})
                columns = st.columns(3)
                columns[0].metric('模型规模', info.get('parameter_size', '未获取'))
                columns[1].metric('模型架构', info.get('architecture', '未获取'))
                columns[2].metric('量化方式', info.get('quantization', '未获取'))
                st.caption('参数规模中的 B 表示十亿个参数，例如 8.2B 约为 82 亿；量化方式来自模型文件元信息。')
                if cached.get('error'):
                    st.warning('本地 AI 不可用：' + cached['error'])
                effective_context = info.get('context')
                st.dataframe([
                    {'推理参数': '本次上下文窗口', '当前值': f'{effective_context} tokens' if effective_context else f'配置 {config.num_ctx} tokens，模型上限待读取'},
                    {'推理参数': '模型原生上下文上限', '当前值': f'{info["model_context"]} tokens' if info else '未获取'},
                    {'推理参数': '生成温度 / 重复惩罚', '当前值': '0 / 1.1'},
                    {'推理参数': '思考模式', '当前值': '关闭，仅使用最终回答'},
                    {'推理参数': '各阶段输出上限', '当前值': f'标准 {min(config.max_tokens,1536)} / 个人分析 {min(config.max_tokens,2048)} / 讲评 {min(config.max_tokens,1536)} tokens'},
                    {'推理参数': '单次请求超时', '当前值': f'{config.timeout:g} 秒'}], hide_index=True, width='stretch')
                st.caption('上下文取配置值与模型实际上限的较小值；超限会明确拒绝，不截断。模型由 Ollama 自动调度 GPU。')
            else:
                st.subheader('DeepSeek 外部 API')
                st.write('模型名称：')
                st.code(config.model, language=None)
                st.caption('接口地址：' + config.base_url)
                if config.api_key.strip():
                    st.success('API Key 已从环境变量读取，页面不会展示密钥。')
                    if os.getenv('TEAM_DEMO', '').lower() == 'true':
                        st.caption('团队演示配置已就绪，可直接载入匿名样例，无需再填写接口或密钥。')
                else:
                    st.warning('尚未配置 DeepSeek API Key。请在本机 .env 文件或进程环境变量中设置 API_KEY。')
                st.caption(f'请求超时 {config.timeout:g} 秒；JSON 输出；三个 AI 阶段均使用 DeepSeek 接口。')
                with st.expander('查看 DeepSeek 环境变量配置示例'):
                    st.code('API_BASE_URL=https://api.deepseek.com\nAPI_KEY=填写自己的 DeepSeek API Key\nAI_MODEL=deepseek-flash\nAI_TIMEOUT=60', language='dotenv')
                    st.caption('密钥只从环境变量读取；修改后需重启应用以加载新配置。外部与本地模型的配置相互独立。')
    except ValueError as exc:
        st.error(str(exc))
    st.caption('每文件 ≤5 MiB，提取原文 ≤20,000 字符，PDF ≤60 页；每批最多 15 份。文件名：学号_说明.扩展名。')
    roster = st.file_uploader('学生名单 CSV（student_id,name）', type=['csv'])
    requirement = st.file_uploader('作业要求', type=['txt', 'docx', 'pdf'])
    submissions = st.file_uploader('学生作业（可多选）', type=['txt', 'docx', 'pdf'], accept_multiple_files=True)
    if st.button('读取上传并建立新批次', disabled=new_batch_unavailable):
        if not roster or not requirement or not submissions:
            st.error('请上传名单、作业要求和至少一份作业')
        else:
            try:
                new = create_batch(roster.getvalue(), (requirement.name, requirement.getvalue()),
                                   [(f.name, f.getvalue()) for f in submissions], mode)
                install_batch(new)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if st.button('载入匿名样例（10 份，按当前模式分析）', disabled=new_batch_unavailable):
        root = Path(__file__).parent / 'samples'
        install_batch(create_batch((root/'roster.csv').read_bytes(), ('requirements.txt', (root/'requirements.txt').read_bytes()),
                                   [(p.name, p.read_bytes()) for p in sorted((root/'assignments').iterdir())], mode=mode))
        st.rerun()
    if batch:
        st.caption(f'当前批次：{len(batch.roster)} 人、{len(batch.documents)} 份作业；模式 {batch.mode}。上述模式选择只作用于新批次。')
        groups, rows = match_documents(batch.roster, batch.documents)
        st.dataframe(rows, width='stretch', hide_index=True)
        for sid, docs in groups.items():
            if len(docs) > 1:
                valid = {d.key: d for d in docs if d.status == '正常'}
                options = [None] + list(valid)
                choice = st.selectbox(f'{sid} 重复提交：选择一份', options,
                    index=options.index(batch.selected.get(sid)) if batch.selected.get(sid) in options else 0,
                    format_func=lambda k: '暂不分析' if k is None else f'{valid[k].filename} [{k}]',
                    key=f'duplicate_{st.session_state.token}_{sid}')
                if choice != batch.selected.get(sid):
                    select_submission(batch, sid, choice)
                    st.session_state.token = uuid4().hex
                    st.rerun()
        with st.expander('作业要求原文与段落'):
            st.json(dict(enumerate(batch.requirement.paragraphs, 1)))
        if st.button('阶段一：提取标准 / 重试', disabled=batch.mode == 'mock' or (batch.mode == 'ollama' and not local_inference_enabled())):
            try:
                with st.spinner('提取标准中'):
                    criteria = AIClient(batch.mode).extract_criteria(anonymize(batch.requirement.text, batch.roster))
                st.session_state['criteria_editor_' + st.session_state.token] = criteria.model_dump_json(indent=2)
                st.success('已生成评价标准草稿，请检查、修改后确认。')
            except AIError as exc:
                st.error(str(exc))
        default = batch.criteria.model_dump_json(indent=2) if batch.criteria else ''
        edited = st.text_area('标准 JSON（3～5 个维度；可编辑名称、检查要点及章节）', default,
                              height=300, key='criteria_editor_' + st.session_state.token)
        if st.button('确认此评价标准'):
            try:
                criteria = Criteria.model_validate_json(edited)
                changed = batch.criteria != criteria
                confirm_criteria(batch, criteria)
                if changed:
                    st.session_state.token = uuid4().hex
                    st.rerun()
                st.success('标准已确认。标准变化时清除旧分析、审核及报告。可进入第二页。')
            except ValueError:
                st.error('标准 JSON 无效，请核对字段、唯一 D1～D5 ID、3～5 个维度和非空检查要点、章节。')
        if batch.criteria:
            st.success('已有确认标准；编辑器中的修改须再次点击确认才生效。')

elif page == '个人分析与审核':
    if not batch or not batch.criteria:
        st.info('请先建立批次并确认评价标准')
    else:
        st.caption(f'可分析 {len(batch.selected)} 份。已成功 {len(batch.results)} 份，失败 {len(batch.errors)} 份。')
        if st.button('阶段二：分析所有未成功项', disabled=not batch.selected or batch.mode == 'mock' or (batch.mode == 'ollama' and not local_inference_enabled())):
            try:
                client = AIClient(batch.mode)
                targets = [sid for sid in batch.selected if sid not in batch.results]
                progress = st.progress(0.0)
                for index, sid in enumerate(targets):
                    analyze_one(batch, sid, client)
                    progress.progress((index + 1) / len(targets), text=f'已处理 {index + 1}/{len(targets)}')
                st.rerun()
            except AIError as exc:
                st.error(str(exc))
        for sid, error in batch.errors.items():
            st.error(f'{sid}：{error}（可在下方选择该项重试）')
        if batch.selected:
            sid = st.selectbox('选择学生', list(batch.selected), format_func=lambda x: f'{x} {batch.roster[x]}')
            doc = next(d for d in batch.documents if d.key == batch.selected[sid])
            st.write('选定文件：', doc.filename)
            st.json(objective_checks(doc, batch.criteria))
            with st.expander('编号原文（核对 AI 引用）'):
                for i, paragraph in enumerate(doc.paragraphs, 1):
                    st.text(f'[{i}] {paragraph}')
            if st.button('分析 / 单项重试（覆盖该项旧结果）', disabled=batch.mode == 'mock' or (batch.mode == 'ollama' and not local_inference_enabled())):
                try:
                    with st.spinner('分析中'):
                        analyze_one(batch, sid, AIClient(batch.mode))
                    # 更换编辑器版本，避免旧草稿覆盖重试结果。
                    st.session_state.token = uuid4().hex
                    st.rerun()
                except AIError as exc:
                    st.error(str(exc))
            if sid in batch.results:
                result = batch.results[sid]
                st.json([f.model_dump() for f in result.findings])
                feedback = st.text_area('个人反馈审核稿（可修改）', batch.feedback[sid], height=200,
                                        key=f'feedback_{st.session_state.token}_{sid}')
                if st.button('保存反馈并标记已审核'):
                    if not feedback.strip() or len(feedback) > 5000:
                        st.error('反馈应为 1～5000 字符')
                    else:
                        batch.feedback[sid] = feedback.strip()
                        batch.reviewed.add(sid)
                        st.success('反馈已保存并审核')
                st.caption('审核状态：' + ('已审核' if sid in batch.reviewed else '待审核') + '；只有点击保存的文本会进入导出。')

else:
    if not batch or not batch.criteria or not batch.results:
        st.info('请先成功分析至少一份作业')
    else:
        summary = batch_summary(batch)
        st.json(summary)
        st.caption(f'反馈审核：{len(batch.reviewed)}/{len(batch.results)}。缺交、未选重复项及失败项不进入完成比例分母。')
        if st.button('阶段三：仅发送统计生成讲评 / 重试', disabled=batch.mode == 'mock' or (batch.mode == 'ollama' and not local_inference_enabled())):
            try:
                with st.spinner('生成讲评中'):
                    batch.outline = AIClient(batch.mode).class_outline(summary, batch.criteria)
                batch.report = batch.outline.summary + '\n\n' + '\n'.join(f'{i}. {p}' for i, p in enumerate(batch.outline.outline, 1))
                batch.report_reviewed = False
                st.session_state['report_' + st.session_state.token] = batch.report
            except AIError as exc:
                st.error(str(exc))
        if batch.report:
            report_key = 'report_' + st.session_state.token
            if report_key not in st.session_state:
                st.session_state[report_key] = batch.report
            report = st.text_area('班级讲评审核稿', height=250, key=report_key)
            if st.button('保存讲评并标记已审核'):
                if report.strip() and len(report) <= 15000:
                    batch.report = report.strip()
                    batch.report_reviewed = True
                    st.success('讲评已保存并审核')
                else:
                    st.error('讲评应为 1～15000 字符')
            if batch.reviewed == set(batch.results) and batch.report_reviewed:
                st.download_button('下载最终 ZIP（已保存审核稿）', data=build_zip(batch),
                                   file_name='coursework_feedback.zip', mime='application/zip')
            else:
                st.info('完成所有已分析反馈和班级讲评的审核后，可下载 ZIP。')
