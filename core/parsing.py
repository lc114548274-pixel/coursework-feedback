import re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from docx import Document as WordDocument
from pypdf import PdfReader
from .models import Document, MAX_BYTES, MAX_TEXT

def parse_document(filename: str, data: bytes, key: str) -> Document:
    doc = Document(key, filename)
    try:
        if len(data) > MAX_BYTES:
            raise ValueError('文件超过 5 MiB，拒绝处理，不会截断')
        if not data:
            doc.status = '空文件'
            return doc
        suffix = Path(filename).suffix.lower()
        if suffix == '.txt':
            text = data.decode('utf-8-sig')
        elif suffix == '.docx':
            # 防止小压缩包展开为过大文档；所有解析均使用内存流。
            with ZipFile(BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist()) > 30 * 1024 * 1024:
                    raise ValueError('DOCX 解压体积超过 30 MiB')
            word = WordDocument(BytesIO(data))
            text = '\n'.join([p.text for p in word.paragraphs] +
                             [' | '.join(c.text for c in r.cells) for t in word.tables for r in t.rows])
        elif suffix == '.pdf':
            reader = PdfReader(BytesIO(data))
            if len(reader.pages) > 60:
                raise ValueError('PDF 超过 60 页')
            text = '\n'.join(p.extract_text() or '' for p in reader.pages)
            if not text.strip():
                raise ValueError('可能是扫描件，首版暂不支持 OCR')
        else:
            raise ValueError('仅支持 TXT、DOCX、文字型 PDF')
        # 对提取原文也设限，不能靠清理空白绕过长度限制。
        if len(text) > MAX_TEXT:
            raise ValueError(f'提取文本超过 {MAX_TEXT} 字符，不会截断')
        doc.paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in text.splitlines() if p.strip()]
        doc.text = '\n'.join(doc.paragraphs)
        if not doc.text:
            doc.status = '空文件'
    except Exception as exc:
        doc.status = '解析失败'
        doc.error = str(exc) if isinstance(exc, (ValueError, UnicodeError)) else '文件格式损坏或无法解析'
        if filename.lower().endswith('.pdf') and '扫描件' not in doc.error:
            doc.error += '；若无可提取文字，可能是扫描件，首版暂不支持 OCR'
    return doc
