from collections import Counter
from .models import Criteria, Analysis

def summarize(criteria: Criteria, results: dict[str, Analysis], total: int) -> dict:
    dimensions = []
    for dim in criteria.dimensions:
        findings = [f for r in results.values() for f in r.findings if f.dimension_id == dim.id]
        counts = Counter(f.status for f in findings)
        problems = Counter(p.strip() for f in findings for p in set(f.problems) if p.strip())
        dimensions.append({'id': dim.id, 'name': dim.name, '已分析人数': len(findings),
                           '完成': counts['完成'], '部分完成': counts['部分完成'], '未完成': counts['未完成'],
                           '完成比例': round(counts['完成'] / len(findings), 4) if findings else None,
                           '常见问题': [{'问题': p, '人数': n} for p, n in problems.most_common(10)]})
    return {'名单人数': total, '成功分析人数': len(results), '未纳入统计人数': total-len(results),
            '口径': '比例分母为成功分析人数；同维度同问题每人计一次；问题文本按完全相同合并，属于辅助分析统计。',
            'dimensions': dimensions}
