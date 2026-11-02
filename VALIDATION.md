# 实际验证记录

验证日期：2026-10-29（Asia/Seoul）。Python 3.12.7，Windows PowerShell。

## 依赖及启动

- 已实际执行 `python -m pip install -r requirements.txt`、`python scripts/generate_samples.py`。
- 已实际执行 `python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8501`。
- 服务输出 `Uvicorn server started on 127.0.0.1:8501`。
- `http://127.0.0.1:8501/_stcore/health` 与首页 `/` 实际 HTTP 检查均返回 200。
- 验证版本：Streamlit 1.66.1、pydantic 2.13.5、python-docx 1.2.0、pypdf 6.21.4、httpx 0.28.1、pytest 7.4.4。

## 自动测试

实际运行命令：`python -m pytest -q`。初版为 40 项；团队演示配置修改后：**94 passed**。

- UTF-8 / BOM 名单、前导零保留、重复学号拒绝、缺交、重复提交、名单外文件、精确学号匹配。
- 三种真实格式样例解析；零字节、纯空白、无文字 PDF、损坏 DOCX、错误编码、文件及文本限额。
- 独立章节标题的命中依据、非空白字符数、按成功分析人数计算比例、同人同问题去重。
- 三阶段 JSON 契约；缺字段、多字段、非法 JSON、无效维度 ID、重复 ID、越界引用、布尔值冒充编号、空白反馈。
- MockTransport 验证 HTTP 429、超时、空响应、坏 JSON、封装字段缺失、截断返回；不访问真实服务。
- 去标识化及阶段三仅发送 statistics；缺少真实 Key 时拒绝 real 模式。
- 单份失败不中断其他份、重试恢复、标准和提交选择改变后的结果失效、重复提交必须手选且不能选择解析失败文件。
- 10 份作业业务闭环全部使用内存，ZIP 检查 10 份反馈、班级报告和处理清单；测试在业务分析及导出阶段拦截文件写入。
- Streamlit AppTest：以内存文件流注入上传接口 → 读取名单和 10 份文件 → 生成和确认标准 → 批量分析 → 逐份修改保存审核 → 生成讲评 → 修改审核 → 下载控件生成 ZIP，直接解包验证教师修改稿。测试运行真实应用脚本和控件事件，未操作浏览器原生选文件窗口或实际保存下载文件。
- UI 回归：更改标准后重新分析，不沿用旧反馈编辑器内容。
- Ollama 回归：无需 Key 的三阶段原生协议、只有本机地址可用、IPv6、/v1 地址归一、模型真实上下文上限、输出截断和封装错误、思考字段分离、一次定向纠错且不无限循环、章节候选来自原文、状态与证据联合约束。单测与本机 .env 隔离，单测绝不调用实际模型。
- 页面回归包含 Ollama 模式选择、原生客户端路由及三阶段调用；真实本地模型验证另见下节。
- “未知运行模式”回归：统一规范 UI 标签、批次和客户端模式值；模拟已经运行的进程缓存旧 AI 客户端，验证按版本重载后旧批次对象、10 份作业仍保留，Ollama 可正常初始化。不通过重启服务或清空会话修复，不把未知模式自动降级为 mock。

## Ollama 真实本机验证

本地 Ollama 0.40.13；NVIDIA GeForce RTX 4060 Laptop GPU，8188 MiB 显存；物理内存约 16GB。服务初始未启动，已在后台启动本机 Ollama 服务。

发现并修正：

1. 原项目只允许 HTTPS / API Key，阻止了本地接入。新增独立 `ollama` 模式，原生 `/api/chat`、本机地址限制、不发送 Authorization，云端 real 仍保持 HTTPS / Key 要求。
2. 本机 `deepseek-r1:latest` 实际架构为 `qwen3`、8.2B、Q4_K_M，却使用 GGUF 中的 DeepSeek R1 模板；短请求设置 think=false 仍只有思考内容，128 token 耗尽无最终回答，标准提取曾超过 180 秒。
3. Gemma 虽单份可跑通，但出现反馈字符串重复、输出截断、空证据等问题；同时 `ollama ps` 显示 9.7GB、37% CPU / 63% GPU，不能作为这台 8GB 显卡的优先配置。
4. 新建 `coursework-qwen3:8b`，复用已有 Qwen3 权重，不下载、不覆盖来源。正确 ChatML 模板、显式 `parser=qwen3`、停止词与非思考前缀。第一次仅设置 Go 模板时，服务仍选用 GGUF 模板；经 `/api/show.template_source` 验证后改用显式 PARSER，最终模板来源为 `parser`，实际模板含正确的 `<|im_start|>`。
5. 默认上下文从 16384 降为 8192，原权重 16K 配置是 20% CPU / 80% GPU；修正后的 8K 配置实测 **6.2GB、100% GPU**。推理过程中 `nvidia-smi` 显示显存占用 7221 MiB、GPU 利用率 97%。这说明 CPU 原来参与部分层推理，且任务管理器 3D 图不能代替 CUDA 指标；100% GPU 后 CPU 仍承担 HTTP、分词、Python 解析和页面工作。
6. 本地采用短 JSON 示例与简体中文输出要求、按阶段限制生成长度、状态和证据联合 Schema、一次定向结构纠错。对超出模型实际上下文的输入明确拒绝，不截断。

实际执行：

```powershell
python scripts/prepare_ollama_model.py
python scripts/test_ollama_live.py --model coursework-qwen3:8b --limit 10
ollama ps
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

最终 10 份真实本地推理结果：

- 阶段一提取 3 个有效维度，输出为简体中文，必需章节对应原文三个标题，约 2.7 秒。
- 集成脚本明确模拟教师修改并确认标准，再分析 6 TXT、3 DOCX、1 文字 PDF。
- 阶段二 **10/10 成功**，每份约 **6.0～8.9 秒**，全部 `done_reason=stop`，全部通过严格校验，**0 次自动纠错**。
- 阶段三仅根据 Python 统计摘要，生成 3 条班级讲评；通过 JSON 和维度 ID 校验。
- 模拟逐人反馈修改、审核与讲评审核；内存 ZIP **17684 字节**，解包完整性、10 份反馈及教师修改标记检查通过。
- 完整流程 **73.9 秒**。这是此批匿名短样例的热启动实测，不代表 20,000 字长文的耗时。
- 再次执行准备脚本验证幂等性，已修正目标模型保持不变。
- 额外实际执行 `python scripts/test_ollama_ui_live.py`：真实 Streamlit 页面脚本调用真实 Ollama（没有 MockTransport），完成标准提取和模拟教师修改确认、**10/10** 个人分析、逐人修改保存审核、真实班级讲评、讲评修改审核、下载按钮及 ZIP 解包检查，**80.2 秒**，内存 ZIP **18159 字节**。使用 AppTest 驱动控件事件，未操作浏览器原生文件选择窗口或把 ZIP 保存到磁盘。测试发现并修复了旧版宽度参数弃用提示、讲评编辑器默认值与 Session State 重复设置警告，随后重跑页面回归测试。

本机已创建忽略提交的 `.env`，默认选 Ollama 模式及上述修正模型；源码压缩包排除 `.env`，提供不含密钥的 `.env.ollama.example`。

## 2026-11-02 首页与服务配置修改

- 首页仅保留“外部 API（DeepSeek）”和“本地模型（Ollama）”，删除 mock 选项及演示按钮。旧演示批次不删除，但禁止继续运行模拟分析；内部模拟实现仅用于离线测试与旧数据兼容。
- 本地信息卡从 Ollama `/api/show` 读取模型规模、架构、量化和原生上下文上限，并显示与实际请求一致的上下文、温度、重复惩罚、思考模式、输出上限及超时。实际读到 `coursework-qwen3:8b`、`qwen3`、`8.2B`、`Q4_K_M`、原生上限 131072、本次上下文 8192。
- DeepSeek 配置为 `API_BASE_URL=https://api.deepseek.com`、`AI_MODEL=deepseek-flash`、`API_KEY`；本地使用独立 `OLLAMA_BASE_URL` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT`，避免切换模式时混用地址、Key 和模型。DeepSeek 默认值依据官方当前接口及 JSON 输出文档核对。
- 页面显示 Key 是否已配置，绝不输出 Key。测试覆盖 Key 不出现在代码框、提示、成功消息等渲染内容中，也不进入本地请求。
- 样例按钮按当前所选真实模式建批次；导入后保持所选模式，不自动跳回本地模型。
- 90 项回归测试通过，新增两模式限定、元信息查询失败时页面可用、DeepSeek 未配置 Key 提示、外部与本地配置隔离、密钥保留及旧本地环境变量迁移、元信息不硬编码等验证。
- 再次实际运行新版 `scripts/test_ollama_ui_live.py`：使用两个新模式入口、独立 `OLLAMA_*` 配置与本机 Qwen3，完成标准提取、10/10 作业分析、模拟逐份修改审核、班级讲评及内存下载检查。总耗时 83.7 秒，内存 ZIP 18041 字节；没有自动保存反馈或压缩包。DeepSeek Key 仍未配置，未调用付费外部接口。

## 2026-11-02 DeepSeek 真实调用与团队演示包

- 按明确授权，将提供的共享 Key 配置到忽略提交的 `.env`；没有写入业务源码、测试或文档，也未在输出中回显。
- `GET https://api.deepseek.com/models` 认证返回 HTTP 200，支持 `deepseek-flash` 与 `deepseek-v4-pro`。使用 `deepseek-flash` 非思考模式和 JSON 输出实际测试。
- 运行 `python scripts/test_deepseek_live.py`，真实 Streamlit 页面调用真实 DeepSeek：标准提取 → 模拟教师编辑确认 → 10/10 作业分析 → 逐份模拟修改保存审核 → 班级讲评 → 讲评修改审核 → 下载控件和内存 ZIP 解包检查。
- **12 次实际请求，46.5 秒**；prompt 8139 tokens，completion 4938 tokens，合计 **13077 tokens**。最终反馈 ZIP **25107 字节**，10 份反馈与模拟教师修改标记检查通过；没有自动把反馈落盘。
- 测试同时模拟团队配置：默认 DeepSeek，Key 已就绪；切换本地模式显示“本地 AI 不可用”，查询、建批次与本地推理入口禁用。底层 AIClient 也拒绝本地推理，不能靠绕过页面调用。
- 提供专用团队打包脚本，随包生成 `TEAM_DEMO=true`、`AI_MODE=real`、`OLLAMA_ENABLED=false` 的共享 `.env`；普通源码及配置模板仍无真实 Key。本地开发配置不因此强制关闭本机模型。
- 新增 Windows 启动脚本及跨平台 Python 启动器：独立虚拟环境、锁定依赖安装、配置检查、空闲端口选择、打开页面。仅首次安装依赖需额外下载；同学无需配置接口或安装 Ollama。
- 单测覆盖包含共享配置但 Key 只出现在包内 `.env`、本地禁用时不产生请求、团队页面默认外部模式及本地按钮禁用。打包测试发现 Windows ZIP 路径分隔符差异，已统一修正为 `/`。
- 将团队 ZIP 解压到全新目录（路径包含空格），运行 `python start_demo.py --check`，实际创建全新的 `.demo_venv` 并安装锁定依赖，无需手工填 Key。检查输出配置已就绪、本地 AI 为 False。
- 在全新目录实际运行 `启动演示.bat --no-browser --port 8512`，服务启动成功且健康检查 HTTP 200。用该独立环境运行真实页面脚本，确认默认 DeepSeek 和共享配置提示；切换本地显示不可用、相关按钮禁用；没有请求实际模型或打印 Key。
- 在新解压目录及独立虚拟环境中再次运行全部测试，**94 passed in 9.10s**。测试脚本已与团队 `.env` 隔离，不会因包内关闭本地模式而影响旧进程兼容性测试，也不会在单测中调用付费服务。

## 当前边界

DeepSeek 与本机 Ollama 均已真实测试，不是 mock。其他外部服务未实测。团队启动器需要电脑先有 Python 3.10+ 和网络，未捆绑 Python 解释器或本地模型权重。

mock 标准为固定模板，个人分析为章节关键词演示，不代表语义质量判断。无 OCR，复杂 PDF 顺序和 DOCX 文本框未覆盖。引用结构可校验，但引用是否支持判断、模型是否遵守无评分和抗提示注入要求，必须由教师人工核对。

项目代码和匿名样例保存在目录中；真实上传内容不落盘。没有数据库、ORM、账号、登录、持久化结果或跨会话缓存。


## 团队包本地入口恢复（最新配置）

根据最新展示要求，团队包 OLLAMA_ENABLED 改为 true，保留本地模型查询及推理入口。以上本地禁用记录为旧版验证记录。DeepSeek 默认配置不变；本地模型需在演示电脑安装 Ollama 并准备权重，安装说明见同学演示说明.md。

本次修改后实际运行全部单元及页面测试：95 passed。新增团队配置下切换本地、创建本地批次并提取标准的页面回归测试（替身接口，不产生付费调用）。
