"""仅生成仓库匿名样例，不是应用处理上传内容的路径。"""
from pathlib import Path
from io import BytesIO
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

def text_pdf(text):
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 12 Tf 50 780 Td (' + text + ') Tj ET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

def generate(root):
    (root/'assignments').mkdir(parents=True, exist_ok=True)
    (root/'edge_cases').mkdir(exist_ok=True)
    roster = 'student_id,name\n' + ''.join(f'2023{i:03d},匿名学生{i:02d}\n' for i in range(1, 11))
    (root/'roster.csv').write_text(roster, encoding='utf-8-sig')
    (root/'requirements.txt').write_text('请完成一个 Python 文件分析实验。\n任务目标\n阐明背景、目标及输入输出。\n方法实现\n说明解析、校验和错误处理，附关键证据。\n结果反思\n展示测试结果，分析限制及改进方向。\n不要自动评分。', encoding='utf-8')
    for i in range(1, 11):
        text = f'任务目标\n本实验研究第 {i} 类文件的可靠处理。\n方法实现\n读取内存字节流，校验输入并执行处理。'
        if i % 3:
            text += '\n结果反思\n普通输入能够处理，异常样例仍需补充。'
        if i <= 6:
            (root/'assignments'/f'2023{i:03d}_作业.txt').write_text(text, encoding='utf-8-sig' if i % 2 else 'utf-8')
        elif i <= 9:
            doc = Document()
            for line in text.splitlines():
                doc.add_paragraph(line)
            doc.save(root/'assignments'/f'2023{i:03d}_作业.docx')
        else:
            (root/'assignments'/f'2023{i:03d}_assignment.pdf').write_bytes(text_pdf('Task goal: test in-memory extraction. Method: parse text. Results: review limitations.'))
    edge = root/'edge_cases'
    (edge/'2023001_重复.txt').write_text('任务目标\n这是一份重复提交。', encoding='utf-8')
    (edge/'9999999_名单外.txt').write_text('名单外示例', encoding='utf-8')
    (edge/'2023002_空文件.txt').write_bytes(b'')
    blank = PdfWriter()
    blank.add_blank_page(width=595, height=842)
    blank.write(edge/'2023003_无文字.pdf')
    (edge/'2023004_损坏.docx').write_bytes(b'not a docx')
    (edge/'duplicate_roster.csv').write_text(roster + '2023001,重复匿名学生\n', encoding='utf-8')
    (edge/'roster_missing.csv').write_text(roster + '2023011,匿名学生11\n', encoding='utf-8')

if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1]/'samples')
