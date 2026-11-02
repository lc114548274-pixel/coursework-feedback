import re
from .models import Document, Criteria

def objective_checks(doc: Document, criteria: Criteria) -> dict:
    sections = []
    for section in criteria.required_sections:
        # 明确采用标题行规则，正文提及章节名不算已提供章节。
        hits = [i for i, p in enumerate(doc.paragraphs, 1)
                if re.sub(r'^[\s#\d一二三四五六七八九十、.．（）()：:]+', '', p).strip() == section.strip()]
        sections.append({'章节': section, '存在': bool(hits), '段落编号': hits})
    return {'文件状态': doc.status, '非空白字符数': len(re.sub(r'\s', '', doc.text)),
            '段落数': len(doc.paragraphs), '必需章节': sections,
            '依据': '字数为去除空白后的字符数（含标点）；章节仅匹配独立标题行，去除常见编号。无自动评分。'}
