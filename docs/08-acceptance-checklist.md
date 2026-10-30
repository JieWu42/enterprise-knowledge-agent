# 题目要求与验收证据对照

本表按项目要求归纳核对，不复制完整试题。结论针对当前提交的实现、开发用例和实际记录，不表示所有未知输入均可靠，也不作为分数预测。

追加检索迭代后，24 项确定性工程测试通过，17 项真实模型用例自动断言通过；对应记录的源码、词表摘要及引用来源已重新核对。最新结构化结果见 [retrieval-iteration.json](../examples/acceptance-audit/retrieval-iteration.json)。上一轮针对 15 项存档的核查保留为 [audit.json](../examples/acceptance-audit/audit.json)，对应旧版本，不覆盖为新结果。

## 通用交付与执行要求

| 要求 | 结果与证据 |
| --- | --- |
| CLI、HTTP API、Notebook 至少一种可运行入口 | CLI；[README](../README.md)提供环境、变量、真实模型、离线与测试命令；[run.py](../run.py)为入口 |
| README、源码、测试、示例、资料、五份文档、依赖和变量模板 | 均已纳入仓库；见根目录、src、tests、examples、data 与 docs/01 至 05 |
| 文档资料包含 ID 与版本日期 | [合成制度](../data/documents.json)包含 id、version_date、scope 与段落编号 |
| 检索与片段读取工具 | [tools.py](../src/knowledge_agent/tools.py)提供 search_documents 与 read_document |
| 真正的模型选择动作、执行、观察、调整循环 | [agent.py](../src/knowledge_agent/agent.py)将模型原生工具调用交给执行器，再把实际观察传回模型；真实模式没有按用例写死动作 |
| 至少两条随工具结果变化的实际路径 | [自然冲突 Trace](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/natural-conflict/trace.json)请求确认；[明确替代 Trace](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/explicit-replacement/trace.json)读取替代条款后回答 |
| 记录步骤、参数、返回、后续动作与简要依据 | Trace 保存 steps、model_response、tools.arguments、observation、最终 decision_summary；上述两条记录保留了动作简述，不记录隐藏思维链 |
| 执行上限与明确未完成状态 | 默认最多 8 次模型调用、10 次工具调用；[超限记录](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/step-limit/output.json)为 incomplete/step_limit；工程测试还覆盖批量工具调用的预算 |
| 至少三组输入、实际输出及 Trace，覆盖正常、资料不足、工具失败 | 最新评测目录分别包含 normal、user-annual-leave、persistent-failure 等；每组均有 input.json、output.json 与 trace.json |
| 测试结果位于 examples，评估文档引用对应材料 | [工程测试报告](../examples/test-results/)与[最新真实评测汇总](../examples/retrieval-improvement/real-model/20261030T202847Z_1e53c7ad/summary.json)均有保留；[评估文档](03-evaluation.md)链接到对应文件 |
| 离线 Mock 与能力边界 | README 提供 --mode mock；固定流程返回 incomplete/mock_only，明确不证明真实模型决策 |
| AI 使用、个人贡献、实际用时、未完成部分及复盘 | [AI 使用记录](04-ai-usage.md)、[复盘](05-retrospective.md)、[贡献记录](06-contribution-log.md)；本人报告约 2.8 小时，保留本人用例与独立运行证据 |
| 框架及版本说明 | 使用 Python 标准库原生实现，未采用 Agent 框架；环境 Python 3.9.13，模型请求名与服务端返回名分别记录 |
| GitHub URL、题号、最终 SHA 与可访问性 | 第 3 题；[仓库](https://github.com/JieWu42/enterprise-knowledge-agent)公开；交付时给出完整 SHA，复现步骤见 [提交说明](07-submission.md) |

## 六类必须验收场景

最新目录基准为 examples/retrieval-improvement/real-model/20261030T202847Z_1e53c7ad，每组均有实际输入、输出、Trace 和断言结果。此前版本的运行记录也继续保留。

| 场景 | 用例 | 实际结果 |
| --- | --- | --- |
| 明确答案 | normal | answered；20 个自然日，引用已读境内差旅制度 |
| 文档冲突 | conflict、natural-conflict | needs_clarification；列出双方规定与引用，不凭新日期裁决 |
| 资料外问题 | out-of-scope | 改写查询补查后 incomplete，说明资料缺口，无伪造引用 |
| 改写后的相似问题 | paraphrase，与 normal 配对 | 找到相同有效资料并保持 20 日结论 |
| 上下文追问 | context | 根据传入历史理解差旅主体与主题，读取原文后列出材料 |
| 工具失败 | transient-failure、persistent-failure | 一次失败后由模型选择重试并取得证据；持续失败时 incomplete，无成功读取的虚假声明 |

## 审核重点与质量边界

- 输出提供 answer、citations（含 document_id、version_date、paragraph_id、quote）、gaps 与 status；引用校验检查已读来源、版本和连续原文片段，保留记录中的引用均通过该检查。
- 同一问题在正文期限由 20 日改为 25 日后，答案随之改变；新增生效及替代条款后，模型从请求澄清转为明确回答，相关记录见 changed-document 与两份配对资料。
- 冲突处理、工具接口和领域词扩展均有对照证据；新增 12 条固定开发查询上的文档级检索消融，见 [检索改进](09-retrieval-improvement.md)。未开展独立盲测、向量检索或大规模召回实验，不作为已完成的大规模检索评测宣传。
- 自动来源校验不等于语义支持保证。当前检索为字符片段匹配与领域词扩展，存在漏检和扩展噪声风险；17 项问答与 12 项检索问题均为开发集验证，不能宣称独立准确率或生产可靠性。
- 持续失败回答仍可能转述带有未核实警告的摘要数值；现有记录明确标记未完成且无引用，但减少此类数值转述仍是可优化点。
- UI、部署、多 Agent、生产级 Runtime 不属于本项目必需交付；独立代码讲解、复杂资料验证及生产适配列入后续工作。
