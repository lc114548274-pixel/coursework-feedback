import csv
import json
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from .matching import match_documents
from .rules import objective_checks
from .workflow import batch_summary

def build_zip(batch) -> bytes:
    if not batch.results or batch.reviewed != set(batch.results) or not batch.report_reviewed or not batch.report.strip():
        raise ValueError('请完成全部已分析反馈及班级讲评的人工审核')
    output = BytesIO()
    def dump(obj):
        return json.dumps(obj, ensure_ascii=False, indent=2)
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        for sid, result in batch.results.items():
            doc = next(d for d in batch.documents if d.key == batch.selected[sid])
            header = f'模式：{batch.mode}（mock 为演示，非真实 AI 分析）\n学号：{sid}\n姓名：{batch.roster[sid]}\n教师已审核，无自动成绩\n\n'
            z.writestr(f'feedback/{sid}.txt', header + batch.feedback[sid])
            z.writestr(f'evidence/{sid}.json', dump({'analysis': result.model_dump(), 'objective': objective_checks(doc, batch.criteria),
                                                  'source_file': doc.filename, 'paragraphs': dict(enumerate(doc.paragraphs, 1))}))
        z.writestr('class_report.txt', f'运行模式：{batch.mode}\n教师已审核；无自动成绩\n\n' + batch.report)
        z.writestr('statistics.json', dump(batch_summary(batch)))
        z.writestr('criteria.json', dump(batch.criteria.model_dump()))
        _, rows = match_documents(batch.roster, batch.documents)
        for row in rows:
            sid = row['学号']
            row['选定文件'] = next((d.filename for d in batch.documents if d.key == batch.selected.get(sid)), '') if sid in batch.roster and row['匹配'] != '名单外文件' else ''
            row['分析状态'] = ('成功/已审核' if sid in batch.reviewed else '成功/待审核' if sid in batch.results else batch.errors.get(sid, '未分析')) if row['匹配'] != '名单外文件' else '未分析'
        csv_out = StringIO()
        writer = csv.DictWriter(csv_out, fieldnames=list(rows[0]))
        writer.writeheader()
        # 防止教师在电子表格中打开时执行上传文件名等不可信内容。
        writer.writerows({k: "'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for k, v in r.items()} for r in rows)
        z.writestr('processing.csv', csv_out.getvalue().encode('utf-8-sig'))
        z.writestr('README.txt', '全部内容由教师主动下载。mock 为固定规则演示；AI 为辅助草稿，无最终成绩。evidence 含原始段落与 AI 原稿，feedback 为教师审核稿。')
    return output.getvalue()
