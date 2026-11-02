import csv
import re
from io import StringIO
from pathlib import Path
from .models import Document, MAX_BYTES

def read_roster(data: bytes) -> dict[str, str]:
    if len(data) > MAX_BYTES:
        raise ValueError('名单超过 5 MiB')
    try:
        reader = csv.DictReader(StringIO(data.decode('utf-8-sig')))
        if reader.fieldnames != ['student_id', 'name']:
            raise ValueError('CSV 列必须按顺序为 student_id,name')
        roster = {}
        for row in reader:
            sid, name = (row.get('student_id') or '').strip(), (row.get('name') or '').strip()
            if None in row or not re.fullmatch(r'[A-Za-z0-9-]{1,40}', sid) or not name:
                raise ValueError('名单存在无效学号、空姓名或多余列')
            if sid in roster:
                raise ValueError(f'名单重复学号：{sid}')
            roster[sid] = name
        if not roster or len(roster) > 200:
            raise ValueError('名单人数应为 1～200')
        return roster
    except UnicodeError as exc:
        raise ValueError('名单必须使用 UTF-8 或 UTF-8-SIG 编码') from exc

def student_id(filename: str) -> str:
    # 完整首段是学号：防止 20230010 错配 2023001。
    return Path(filename).stem.split('_', 1)[0]

def match_documents(roster: dict[str, str], docs: list[Document]):
    grouped = {sid: [] for sid in roster}
    outsiders = []
    for doc in docs:
        sid = student_id(doc.filename)
        (grouped[sid] if sid in grouped else outsiders).append(doc)
    rows = []
    for sid, name in roster.items():
        items = grouped[sid]
        rows.append({'学号': sid, '姓名': name, '匹配': '缺交' if not items else '重复提交' if len(items) > 1 else '正常匹配',
                     '文件': '；'.join(d.filename for d in items),
                     '解析': '；'.join(d.status + (f'：{d.error}' if d.error else '') for d in items)})
    rows += [{'学号': student_id(d.filename), '姓名': '', '匹配': '名单外文件', '文件': d.filename,
              '解析': d.status + ('：' + d.error if d.error else '')} for d in outsiders]
    return grouped, rows
