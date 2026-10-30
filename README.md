# 企业知识问答 Agent

一个面向合成企业制度的 CLI 助手：模型自主检索、读取原文，根据证据继续补查、回答、追问或停止。包含真实模型接口、离线固定流程、执行上限、引用来源校验和实际运行记录。

实际投入约 2.5 小时。核心实现、验证材料和本人三类场景的独立运行已完成；当前为合成资料下的 CLI 原型。[GitHub 仓库](https://github.com/JieWu42/enterprise-knowledge-agent)公开可读。个人工作与 AI 辅助范围见下列记录。

## 评审入口

- [需求与成功标准](docs/01-requirements.md)
- [提交与快速复现](docs/07-submission.md)
- [题目要求与验收证据对照](docs/08-acceptance-checklist.md)
- [模型决策与实现取舍](docs/02-solution.md)
- [实际验证与限制](docs/03-evaluation.md)
- [AI 辅助范围](docs/04-ai-usage.md)和[个人贡献记录](docs/06-contribution-log.md)
- [真实运行目录](examples/evaluation/)：每个用例包含输入、预期、实际输出、Trace 和自动断言；summary.json 汇总状态。
- [最新 15 项真实模型回归](examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/summary.json)及[段落编号改进前后对照](examples/improvement/paragraph-discovery/comparison.md)。21 项工程测试与真实模型测试分开报告。
- [年假问题改进前](examples/first-runs/user-annual-leave/)与[改进后](examples/improvement/after/)。失败表现保留，不用后来的结果覆盖。
- [自然冲突与明确替代对照](examples/scenario-validation/summary.json)：同一个问题，仅增加替代条款后，模型由待澄清转为明确回答。

## 环境与安装

Python 3.9 或以上，无第三方运行或测试依赖。已在 Windows 的 Python 3.9.13 上运行。进入本项目目录后即可执行；可选建立虚拟环境。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

离线运行不需要变量。真实模型需要设置环境变量，模板见 [.env.example](.env.example)；程序不自动读取 .env 文件。

```powershell
$env:DEEPSEEK_API_KEY = "填写你自己的密钥"
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com"
$env:DEEPSEEK_MODEL = "deepseek-chat"
python run.py --question "中国境内员工的境内差旅报销期限是什么？"
```

请求模型名和服务端实际返回模型名都会记入 Trace；模型别名可能变化，以实际运行记录为准。

## 运行与复现

```powershell
# 不调用真实模型，只演示固定的检索、读取、结束流程。
python run.py --mode mock --question "境内差旅报销期限？"

# 制度冲突、部分资料、上下文追问。
python run.py --question "工作餐报销需要在几天内提交？"
python run.py --input examples/inputs/user-annual-leave.json
python run.py --input examples/inputs/context.json

# 一次读取失败，以及持续失败。
python run.py --question "境内差旅报销期限？" --fail-tool read_document --fail-count 1
python run.py --question "境内差旅报销期限？" --fail-tool read_document --fail-count -1

# 限制执行次数。
python run.py --question "境内差旅报销期限？" --max-model-calls 1

# 工程测试，及保存实际测试报告。
python -m unittest discover -s tests -v
python scripts/check_tests.py

# 真实模型评测全部开发用例；会消耗所配置服务的调用额度。
python scripts/evaluate.py --mode real
python scripts/evaluate.py --mode real --cases normal,conflict,user-annual-leave
python scripts/evaluate.py --mode real --cases natural-conflict,explicit-replacement

# 检查已保存的配对运行，不调用 API。
python scripts/check_scenario_runs.py
python scripts/compare_paragraph_discovery.py

# 离线只检查执行流程，不能作为真实模型问答效果。
python scripts/evaluate.py --mode mock
```

每次运行创建独立记录目录，不覆盖之前的输出。CLI 的退出码：0 表示全部回答；2 表示部分回答、待澄清、未完成或 Mock 结束；1 表示配置/输入/文件错误。业务上正确的拒答不等于程序故障，请结合 JSON 的 status 判断。PowerShell 或调用器可能把非零退出包装为一般失败。

状态包括 answered、partially_answered、needs_clarification、incomplete。部分回答保留已确认内容及引用，明确未解决部分；不能将“写了答案”当成全部完成。

## 边界

所有制度为合成测试数据，不代表真实公司规则。小型资料库使用轻量中文检索，未接向量库。引用核验保证已读来源、版本和原文片段匹配，不自动证明语义支持。详见评估文档。

仓库不包含密钥、真实员工数据或完整考试题面。当前本地源码版本通过 Trace 的 source_sha256 关联；正式提交时再固定最终 Git commit SHA。
