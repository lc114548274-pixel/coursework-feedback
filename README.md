# 课程作业多维分析与智能反馈系统

## 团队成员

本项目为团队课程作业，团队成员：B、L（按提供的姓名首字母署名）。

从零编写的 Python 课程项目。三个 Streamlit 页面串起文件解析、标准确认、辅助分析、人工审核、班级统计与 ZIP 下载。没有数据库、ORM、账号或登录功能，没有引用或改造现有业务系统。

## 团队演示包

发给同学的 `coursework_feedback_team.zip` 是单独的团队演示配置：默认 DeepSeek，按团队要求随包包含共享 `.env`，无需同学填写 API Key；本地模型入口保持启用，安装并启动 Ollama 和配置对应模型后即可使用。密钥不写进业务源码，页面也不显示。

解压后，Windows 双击 **启动演示.bat**，启动器自动创建 `.demo_venv`、安装锁定版本依赖、检查配置并打开浏览器。电脑需已安装 Python 3.10+（推荐 3.12），首次安装依赖和调用 DeepSeek 需联网；不需要安装 Ollama、CUDA 或模型。完整步骤见 [同学演示说明.md](同学演示说明.md)。

制作包时在本机环境配置好 Key，再执行 `python scripts/build_team_package.py`。普通源码分发仍排除 `.env`；此专用团队包按明确授权包含共享配置，且不包含本地模型、虚拟环境或上传的学生数据。

## 快速运行（Windows PowerShell / Python 3.12）

```powershell
cd 'C:\Users\LICHUANG\Documents\New project 2\coursework_feedback'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

浏览器打开终端给出的地址（通常为 http://localhost:8501）。首页只提供 **外部 API（DeepSeek）** 和 **本地模型（Ollama）**，默认选本地模型。本地模型无需 API Key，需要先运行 Ollama 并准备模型，见下文。点击“载入匿名样例（10 份，按当前模式分析）”可载入样例，再调用所选真实模型；也可手动上传 `samples` 中的文件。若已有 Python 环境，直接执行 `python -m pip install -r requirements.txt` 和 `python -m streamlit run app.py`。

## 完整操作

1. **上传与标准确认**：上传 `samples/roster.csv`、`samples/requirements.txt` 及 `samples/assignments` 中全部 10 份文件，点击“读取上传并建立新批次”。检查匹配与解析结果。重复提交必须手选有效文件，否则不分析。
2. 点击“阶段一：提取标准 / 重试”，使用所选服务生成标准；修改 JSON 后“确认此评价标准”。可配置 3～5 个维度，ID 唯一且为 D1～D5，每维度至少一个检查要点，至少一个必需章节。
3. **个人分析与审核**：点击批量分析。每份独立处理，失败不阻断其余文件。选择学生查看客观检查、编号原文及 AI 引用；可单项重试。逐份修改反馈并点击“保存反馈并标记已审核”。编辑框修改不会自动替换已保存审核稿。
4. **班级汇总与导出**：查看 Python 统计，生成讲评，编辑并保存审核。全部已分析反馈及讲评审核后出现 ZIP 下载按钮。无需让缺交或解析失败者进入分析，处理清单会列出这些状态。
5. 下载包含 `feedback/学号.txt`、`evidence/学号.json`、`class_report.txt`、`statistics.json`、`criteria.json`、`processing.csv` 及说明。feedback 是教师保存稿，evidence 是原 AI 分析、客观依据及编号原文。

修改确认标准会清除全部旧分析与审核；更改某学生的提交选择或重试会清除该项旧分析、审核及旧班级报告，避免统计混用。切换运行模式必须重新建立批次。

## 真实 AI 配置

```powershell
Copy-Item .env.example .env
# 在本机编辑 .env，填入自己的 API_KEY；不要提交 .env
python -m streamlit run app.py
```

也可直接设置进程环境变量。客户端只读取环境变量；`.env` 由启动层通过 dotenv 载入环境，已有进程变量优先。界面不接受或显示密钥。

### 本地 Ollama（无需 API Key，实际模型推理）

```powershell
ollama serve
# 另开一个 PowerShell，进入本项目：
python scripts/prepare_ollama_model.py
Copy-Item .env.ollama.example .env
# 用 ollama list 核对模型，必要时修改 .env 中的 OLLAMA_MODEL
python -m streamlit run app.py
```

若服务已经启动，不需要重复 `ollama serve`。本机原名为 `deepseek-r1:latest` 的权重，实际 GGUF 架构是 **Qwen3 8.2B Q4_K_M**，但嵌入模板却是 DeepSeek R1。准备脚本先验证架构，再复用已有权重创建 `coursework-qwen3:8b`：正确 ChatML 模板、显式 Qwen3 PARSER、预关闭思考标签、正确停止词。不下载权重、不覆盖来源模型；若同名目标不属于本脚本则拒绝覆盖。其他电脑没有这个来源时，先提供正确的本地 Qwen3 模型并用 `--source 模型名`，或直接把 `OLLAMA_MODEL` 配置为已正确安装的模型。已有 `.env` 时请合并配置、保留自己的 `API_KEY`，不要直接覆盖密钥。

页面选择“本地模型（Ollama）”后新建批次，或点击“载入匿名样例（10 份，按当前模式分析）”。首页显示实际模型名称、参数规模、架构、量化方式、模型上下文上限、本次上下文、生成温度、重复惩罚、思考开关、阶段输出上限和超时；模型元信息来自本机 `/api/show`，查询失败明确显示未获取，不硬编码成某个模型。可点击“刷新本地模型信息”重新查询。

本地模式默认根地址 `http://127.0.0.1:11434`、模型 `coursework-qwen3:8b`、超时 180 秒；使用独立的 `OLLAMA_BASE_URL`、`OLLAMA_MODEL`、`OLLAMA_TIMEOUT` 配置。地址也可填写 `/v1`，客户端会转换为原生 `/api/chat`。仅接受本机 localhost / 127.0.0.1 / ::1，不能把本地模式指向云端。DeepSeek 模式仍要求 HTTPS 和 Key。本地请求不附带 Authorization，不使用系统代理、不调用云端或下载模型。切换模式不会把本地地址和模型传给 DeepSeek，也不会把云端 Key 发给 Ollama。旧版 `.env` 里的本地 `API_*` 配置需要迁移到 `OLLAMA_*`，当前启动层会兼容迁移明确的旧本机地址。

Ollama 使用原生 JSON Schema `format`、`stream=false`、`think=false`、temperature=0；只校验最终 `message.content`，不拼接 `thinking`。请求的 Schema 动态限定确认维度 ID、作业段落编号范围、完成状态与证据的对应关系，并用要求中的短标题作为可选章节以减少幻造。返回后仍执行所有本地校验；首次结构校验失败时只发送错误位置让模型修正一次，第二次仍失败则明确报错并保留人工单项重试，不自动改写判断或伪造依据。不对网络错误自动循环重试。并非 mock，不应据此自动给成绩。

`OLLAMA_NUM_CTX` 默认 **8192**（4096～131072），客户端用 `/api/show` 读取模型实际上下文上限，取两者较小值。8K 是本机 8GB 显卡可全 GPU 加载的实测配置，并非模型最大能力。`OLLAMA_MAX_TOKENS` 默认 4096（512～8192），作为输出全局上限，实际再按阶段取上限：标准及讲评 1536、个人分析 2048。输入按 UTF-8 字节数加模板和输出预留做保守预算，超限直接提示，不截断；这可能拒绝部分实际上能容纳的长文。提高上下文会增加显存和耗时，可能导致 CPU 卸载，且不会突破模型自身上限。非正常结束、模型缺失、断连或超时均显示可重试错误，不降级冒充成功。

### 为什么 CPU 仍有占用

`ollama ps` 的 PROCESSOR 才能判断模型卸载情况；任务管理器默认 3D 图不能代表 CUDA 推理。CPU 仍负责文件解析、HTTP、统计、分词等，模型 100% GPU 也不意味着 CPU 为零。

本机 NVIDIA RTX 4060 Laptop 8GB：原 Gemma 配置显示运行时 9.7GB，**37% CPU / 63% GPU**；原 Qwen 权重配 16K 上下文显示 7.8GB，**20% CPU / 80% GPU**。改为正确模板的 Qwen3、8K 上下文后，`ollama ps` 实测 **6.2GB、100% GPU**，`nvidia-smi` 推理利用率达到 **97%**。CPU 解析和页面线程仍会运行。其他程序占用显存或提高上下文后可能再次部分卸载，应用不会声称始终全 GPU。

```powershell
ollama ps
nvidia-smi
```

显式运行真实本地集成测试（仅发仓库匿名样例，结果与 ZIP 均在内存）：

```powershell
python scripts/test_ollama_live.py --model coursework-qwen3:8b --limit 10
# 另可显式运行真实页面脚本 + 本地模型，仍只使用匿名样例：
python scripts/test_ollama_ui_live.py
```

该脚本在真实模型提取标准后，显式模拟教师按样例要求修改标准、修改反馈和审核用于验证导出，不代表教师真正审核过模型结论；不会保存学生反馈文件。

| 环境变量 | 默认值 / 含义 |
| --- | --- |
| API_BASE_URL | 外部 DeepSeek 根地址，默认 https://api.deepseek.com，不含 /chat/completions |
| API_KEY | DeepSeek API Key，只从环境变量读取，不在界面输入或展示 |
| AI_MODEL | DeepSeek 模型，默认 deepseek-flash，依据官方当前文档配置 |
| AI_TIMEOUT | 外部 API 超时，默认 60 秒，允许 1～600 秒 |
| AI_MODE | 默认 ollama；可设 real，控制首页两个模式的默认选项 |
| OLLAMA_BASE_URL | 本机服务，默认 http://127.0.0.1:11434 |
| OLLAMA_MODEL | 本地模型，默认 coursework-qwen3:8b |
| OLLAMA_ENABLED | 默认 true；团队演示包也为 true，保留本地查询与推理 |
| OLLAMA_TIMEOUT | 本地请求超时，默认 180 秒，允许 1～600 秒 |
| OLLAMA_NUM_CTX | 本地上下文，默认 8192 tokens |
| OLLAMA_MAX_TOKENS | 本地输出总上限，默认 4096；实际再按阶段限额 |
| TEAM_DEMO | 团队包为 true，以随包 .env 为准，默认 DeepSeek 且不依赖同学已有环境变量 |

选择“外部 API（DeepSeek）”，页面显示模型、地址和 Key 是否配置；没有 Key 时给出设置提示，绝不回退为模拟分析。通过 HTTP POST 调用 `{API_BASE_URL}/chat/completions`，使用 `response_format: {"type":"json_object"}`，单次输出上限 6000 token；输出截断视为失败，绝不当成成功结果。未使用系统代理（httpx `trust_env=False`）。

阶段一只发去标识化要求；阶段二只发确认标准及编号段落，不发文件名、名单或本地学号映射，替换正文和标准中与名单完全匹配的姓名、学号；阶段三只发统计摘要。其他联系方式、正文中未在名单出现的身份等不能可靠识别，教师应在使用真实服务前自行移除。真实模式会将文本发送给所配置服务，应了解该服务的数据处理政策。

接口结构和本地严格校验集中在 `core/models.py` 与 `core/ai_client.py`：

```json
{"dimensions":[{"id":"D1","name":"维度名称","checkpoints":["检查要点"]}],"required_sections":["章节标题"]}
```

上面仅展示单个维度的写法，实际必须提供 3～5 个维度。个人分析结构：

```json
{"findings":[{"dimension_id":"D1","status":"部分完成","paragraph_ids":[1],"problems":["问题"],"suggestions":["建议"]}],"feedback":"个人反馈草稿"}
```

实际 findings 必须恰好覆盖确认标准中的全部维度，各 ID 出现一次。完成状态只能是“完成 / 部分完成 / 未完成”；非“未完成”必须引用真实段落，未完成项须有问题与建议。班级结构为 `{"summary":"摘要","outline":["提纲"],"dimension_ids":["D1"]}`，维度 ID 必须属于确认标准。拒绝多余字段、错误类型、缺失字段、空白文本、越界引用及非法 JSON。结构校验不等于事实校验，引用是否真正支持结论仍需教师审核。

## 文件规则与边界

- CSV 必须按顺序为 `student_id,name`，支持 UTF-8 / UTF-8-SIG，学号为 1～40 位字母、数字或连字符，保留前导零；拒绝名单重复学号、空值、额外列。名单 1～200 人。
- 文件名下划线前完整首段（或无下划线时完整文件主名）作为学号，精确匹配，绝不根据姓名猜测。例如 `20230010_作业.txt` 不匹配 `2023001`。
- 每批 1～15 个文件，建议 10～15 份。每文件 ≤5 MiB，提取原文 ≤20,000 字符（清理前检查），PDF ≤60 页，DOCX 解压总大小 ≤30 MiB。超过则明确拒绝，不截断。名单外及解析失败文件也计入 15 份上传限额。
- TXT 采用 UTF-8 / UTF-8-SIG；DOCX 读取普通段落和表格，暂不读取文本框、脚注和图片；PDF 使用 pypdf 提取文字，无文字提示“可能是扫描件，首版暂不支持 OCR”。复杂双栏 PDF 的阅读顺序需人工核对。
- 每个非空文本行清理内部多余空白后成为一个编号段落。DOCX 表格按行附在普通段落之后，PDF 换行由提取器决定。
- 客观“字数”定义为非空白字符数（含标点），不冒称自然语言词数。必需章节采用独立标题行的精确匹配，去除常见编号；正文提到章节名不算，标题变体可能需要教师修改标准。显示命中的段落编号，无自动成绩。
- 维度统计只覆盖成功分析者；比例分母为成功分析人数。常见问题按维度内完全相同文本合并、每人同问题计一次，没有语义聚类，AI 措辞不同可能分开计数。

## 内存处理

上传通过 Streamlit 内存缓冲读取，解析使用 BytesIO；批次仅存 `st.session_state`。没有文件落盘、临时上传文件、数据库、跨会话缓存或内容日志。ZIP 在 BytesIO 中生成，只有教师点击下载后由浏览器保存。应用仅为演示按钮读取仓库匿名样例；`scripts/generate_samples.py` 是开发用样例生成工具，不在真实上传流程调用。

点击“清空本次会话”可清除该会话数据；关闭/刷新连接可能失去结果，不提供恢复或审计持久化。建议本地运行，远程运行时网络与服务端环境由部署者管理。未使用 `st.cache_data` 或 `st.cache_resource` 缓存用户内容。

## 目录

```text
coursework_feedback/
  app.py                    # 三页 UI 与会话状态
  core/
    models.py               # 严格 JSON 模型及内存 Batch / Document 契约
    config.py               # DeepSeek 与 Ollama 独立环境配置
    parsing.py              # TXT / DOCX / PDF
    matching.py             # CSV 和学号精确匹配
    rules.py                # 客观检查与依据
    statistics.py           # Python 班级统计
    ai_client.py            # 三阶段 AI、去标识化、结构校验；内部模拟仅用于单测
    workflow.py             # 批次编排、重试与结果失效管理
    exporting.py            # 内存 ZIP、审核门槛、CSV 导出防公式执行
  samples/
    roster.csv
    requirements.txt
    assignments/            # 6 TXT + 3 DOCX + 1 文字 PDF
    edge_cases/             # 重复、名单外、空文件、无文字 PDF、损坏文件、异常名单
  scripts/generate_samples.py
  scripts/prepare_ollama_model.py  # 复用已有 Qwen3 权重修正模板
  scripts/test_ollama_live.py      # 真实三阶段本地集成
  scripts/test_ollama_ui_live.py   # 真实页面脚本 + 本地模型
  tests/test_core.py
  tests/test_app.py
  tests/test_ollama.py
  .streamlit/config.toml
  .env.example
  .env.ollama.example
  requirements.txt
  pytest.ini
  VALIDATION.md
```

## 验证

```powershell
python -m pytest -q
python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501
```

`test_core.py` 覆盖匹配、解析限额、客观依据、统计、严格结构校验、模拟 HTTP 错误、去标识化、单项失败重试、结果失效与 10 人内存 ZIP 闭环。`test_app.py` 使用 Streamlit AppTest 驱动真实脚本，验证上传接入、三页面、修改全部 10 人反馈、讲评审核及下载按钮的 ZIP 内容。AppTest 上传接入测试注入与 UploadedFile 同等的内存流，不模拟浏览器原生文件选择窗口。

异常演示：正常 10 份中移除对应学生文件，再加 `edge_cases` 下空文件 / 无文字 PDF / 损坏 DOCX；加入重复文件手选；换用 `roster_missing.csv` 可见缺交，`duplicate_roster.csv` 会明确拒绝名单。HTTP 错误由测试注入，不会访问真实服务。

实际结果见 [VALIDATION.md](VALIDATION.md)。DeepSeek 已使用团队提供的 Key 实际跑通 10 份作业及三阶段页面流程；本地 Ollama 实测也单独记录。页面已移除 mock 入口；内部固定规则仅用于离线单测和旧批次兼容，不作为教师可选模型。旧演示批次保留供查看，但禁止继续模拟分析，需建立实际模型批次。提示词把作业视为不可信数据，不提供工具执行能力，仍不能保证模型完全不受提示注入影响，因此严格校验和人工审核不可省略。

参考接口依据：[DeepSeek JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)、[Streamlit 上传的内存存储说明](https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted)。

Ollama 依据：[原生聊天接口](https://docs.ollama.com/api/chat)、[结构化输出](https://docs.ollama.com/capabilities/structured-outputs)、[思考与最终内容分离](https://docs.ollama.com/capabilities/thinking)。
