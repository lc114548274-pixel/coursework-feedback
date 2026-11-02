"""跨模块契约；AI 结构不允许额外字段或类型强制转换。"""
from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 20000
MAX_FILES = 15
MODELS_VERSION = '2026-11-02-two-providers'
MODE_LABELS = {'real': '外部 API（DeepSeek）', 'ollama': '本地模型（Ollama）'}
LEGACY_MODE_LABELS = {'mock': 'mock（无需 Key）', 'real': 'real（环境变量 Key）',
                      'ollama': 'ollama（本地模型，无需 Key）'}

def normalize_mode(value):
    if isinstance(value, str):
        value = value.strip()
        for identifier, label in LEGACY_MODE_LABELS.items():
            if value.lower() == identifier or value in (label, MODE_LABELS.get(identifier)):
                return identifier
    raise ValueError('批次运行模式无效，请重新选择模式建立批次')

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('*')
    @classmethod
    def nonblank_strings(cls, value):
        def visit(item):
            if isinstance(item, str) and not item.strip():
                raise ValueError('文本字段不能只有空白')
            if isinstance(item, list):
                for child in item:
                    visit(child)
        visit(value)
        return value

class Dimension(StrictModel):
    id: str = Field(pattern=r'^D[1-5]$')
    name: str = Field(min_length=1, max_length=80)
    checkpoints: list[str] = Field(min_length=1, max_length=8)

class Criteria(StrictModel):
    dimensions: list[Dimension] = Field(min_length=3, max_length=5)
    required_sections: list[str] = Field(min_length=1, max_length=10)

    @model_validator(mode='after')
    def unique(self):
        ids = [d.id for d in self.dimensions]
        if len(set(ids)) != len(ids):
            raise ValueError('评价维度 ID 不得重复')
        for value in self.required_sections + [c for d in self.dimensions for c in d.checkpoints]:
            if not value.strip() or len(value) > 200:
                raise ValueError('章节及检查要点必须是 1～200 字的非空文本')
        return self

class Finding(StrictModel):
    dimension_id: str
    status: Literal['完成', '部分完成', '未完成']
    paragraph_ids: list[int] = Field(max_length=50)
    problems: list[str] = Field(max_length=10)
    suggestions: list[str] = Field(max_length=10)

class Analysis(StrictModel):
    findings: list[Finding] = Field(min_length=3, max_length=5)
    feedback: str = Field(min_length=1, max_length=5000)

class ClassOutline(StrictModel):
    summary: str = Field(min_length=1, max_length=5000)
    outline: list[str] = Field(min_length=1, max_length=12)
    # 每条提纲对应的统计维度，供本地校验
    dimension_ids: list[str] = Field(min_length=1, max_length=5)

@dataclass
class Document:
    key: str
    filename: str
    text: str = ''
    paragraphs: list[str] = field(default_factory=list)
    status: str = '正常'
    error: str = ''

@dataclass
class Batch:
    roster: dict[str, str]
    requirement: Document
    documents: list[Document]
    selected: dict[str, str] = field(default_factory=dict)
    criteria: Criteria | None = None
    results: dict[str, Analysis] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    feedback: dict[str, str] = field(default_factory=dict)
    reviewed: set[str] = field(default_factory=set)
    mode: str = 'mock'
    outline: ClassOutline | None = None
    report: str = ''
    report_reviewed: bool = False
