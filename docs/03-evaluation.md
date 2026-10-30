# 评估与实际结果

本页记录 2026-10-30 的开发验证。工程测试与真实模型验证分开；下述自动断言不等价于完整语义正确率。

## 环境与结果入口

- Windows，Python 3.9.13，运行和测试均使用标准库，无 Agent 框架。
- 模型请求名 deepseek-chat；首轮服务端返回名为 deepseek-flash，逐步实际名称保存在每份 Trace。
- [首轮完整真实模型运行](../examples/evaluation/20261030T194014Z_9e45c8cf/summary.json)。12 组用例的自动断言均通过。
- [新增自然冲突与明确替代对照](../examples/scenario-validation/summary.json)：2 组真实模型运行通过对应自动断言，见下文。
- [最新完整真实模型回归](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/summary.json)：15 项用例的自动断言均通过。包含原 12 项、两项自然文本对照和一项规则概览反向用例。
- [确定性测试报告目录](../examples/test-results/)。最新 21 项测试通过，0 failures、0 errors；这些测试使用固定响应替身，不证明模型决策效果。
- 最新真实评测源码 SHA256：d38f54a089907ebe53bcb3acd47f304ec1058cb9ad18f22c86c501c70c46220a。首轮源码摘要为 7183914e3b35bfb609e90514fa058351d4efc3106be1332b181e017ff06886c7，各 Trace 保留其对应版本；修改资料用例使用隔离副本。

## 首轮逐例验证

以下文件夹均包含 input.json、expectation.json、output.json、trace.json 和 checks.json。

| 用例与材料 | 预期 | 实际状态及观察 |
| --- | --- | --- |
| [normal](../examples/evaluation/20261030T194014Z_9e45c8cf/normal/output.json) | 明确境内差旅期限，有对应原文 | answered；引用 EXPENSE-CN，20 个自然日 |
| [conflict](../examples/evaluation/20261030T194014Z_9e45c8cf/conflict/output.json) | 同时读取冲突制度，无法裁决则追问 | needs_clarification；引用 MEAL-A 的 7 日与 MEAL-B 的 14 日，未擅自采用新版本 |
| [out-of-scope](../examples/evaluation/20261030T194014Z_9e45c8cf/out-of-scope/output.json) | 不编造期权额度，标明资料缺口 | incomplete；多次改写检索后停止，无引用；reason_code 为 missing_scope 而非预设 out_of_scope，未强制字面一致 |
| [paraphrase](../examples/evaluation/20261030T194014Z_9e45c8cf/paraphrase/output.json) | 与 normal 结论一致 | answered；找回境内差旅原文，20 日 |
| [context](../examples/evaluation/20261030T194014Z_9e45c8cf/context/output.json) | 从历史理解境内差旅，再查所需材料 | answered；发票、审批单、行程记录；期间存在无效段落读取并成功修正 |
| [transient-failure](../examples/evaluation/20261030T194014Z_9e45c8cf/transient-failure/output.json) | 观察一次错误后有限恢复 | answered；首次境内制度读取失败，后续重试成功，错误未从 Trace 删除 |
| [persistent-failure](../examples/evaluation/20261030T194014Z_9e45c8cf/persistent-failure/output.json) | 不把失败读取记为成功 | incomplete/tool_error；无原文引用，明确读取失败 |
| [user-annual-leave](../examples/evaluation/20261030T194014Z_9e45c8cf/user-annual-leave/output.json) | 只回答有依据的流程，资格未知 | partially_answered；保留申请流程，列出带薪资格与额度缺口 |
| [cross-scope](../examples/evaluation/20261030T194014Z_9e45c8cf/cross-scope/output.json) | 国内常驻但境外出差应适用境外办法 | answered；引用境外办法，45 日；曾猜测不存在段落，后续修正 |
| [missing-scope](../examples/evaluation/20261030T194014Z_9e45c8cf/missing-scope/output.json) | 需要确认境内还是境外 | needs_clarification；列出两种条件，未选择单一时限 |
| [step-limit](../examples/evaluation/20261030T194014Z_9e45c8cf/step-limit/output.json) | 仅允许一次模型调用，尚未回答则未完成 | incomplete/step_limit；没有超过上限 |
| [changed-document](../examples/evaluation/20261030T194014Z_9e45c8cf/changed-document/output.json) | 同一问题在正文改成 25 日后改变答案 | answered；引用隔离资料副本中的 25 日，而非原来的 20 日 |

自动检查状态、必要来源 ID、选定关键词、失败事件、缺口及调用上限。AI 已逐例核对关键结论与原文，个人独立语义复核仍需完成；不能将本表标为本人已经亲自验收。

## 真实动态路径

本人独立验收见 [运行与反馈记录](../examples/personal-validation/review.md)：年假部分回答、自然冲突和持续工具失败均已在本人终端执行；后两项由本人反馈“符合预期，没有让员工误解的表达”。AI 核对对应 Trace，确认当前源码、真实模型调用和实际工具结果。

正常路径：模型选择检索 → 读境内办法 → 按范围与期限回答。

冲突路径：模型检索 → 同时读两份工作餐办法 → 发现 7 日/14 日且缺少优先级 → 列出双方引用并请求澄清。

故障恢复路径：模型检索 → 读取返回 tool_unavailable → 模型下一轮再次读取 → 取得真实原文后回答。持续故障时模型有限重试后停止。重试由真实模型提出，执行器没有替它生成重试工具调用。

资料外路径：模型收到无相关原文的检索结果后，自行改写关键词补查，最终说明资料缺口。

详细动作依据见 Trace 中每步 model_response.content 与最终 decision_summary；工具参数及真实返回见 steps.tools。工具调用次数与动作序列并未预设为固定测试日志。

## 本人用例推动的实际改进

输入由吴杰提出：[年假复合问题](../examples/inputs/user-annual-leave.json)。

- [修改前输出](../examples/first-runs/user-annual-leave/20261030T193748Z_15289c7c/output.json)：status=answered，但 gaps 明确表示是否带薪未确认。
- [修改后输出](../examples/improvement/after/20261030T193905Z_41fbb80a/output.json)：status=partially_answered，保留申请流程与证据，明确未解决部分。
- 当前完整回归再次运行该问题，仍返回 partially_answered。两个修改后运行是开发验证，不构成统计稳定性结论。

吴杰选定“部分回答”的产品策略。AI 修改提示和校验并加入工程回归。两者同时变化，本实验验证组合改进，不单独声称某项改动的因果贡献。

## 已知失败与限制

1. 首轮模型在 context 和 cross-scope 中请求了不存在的 p3、p4，工具如实拒绝；随后模型修正并最终回答。后续已增加完整可读编号和错误反馈，并保留下述对照；不能因本轮改善就保证所有未来调用均有效。
2. 持续读取失败的回答仍转述检索摘要中的数值，虽明确注明不能据此确认，但面向员工可能造成误读；可进一步评估是否应完全去掉未核验数值。
3. 来源匹配不证明语义蕴含。normal 等回答使用“从行程结束之日起算”的解释，资料没有精确规定是否含结束当日，不应把它作为精确日期计算依据。
4. 首轮合成冲突文档自述缺少优先级，属于较容易的样例。新增自然文本对照已去掉此提示，见下文；每套仅一次运行，仍未证明对隐含适用范围、多跳冲突或更多自然文本的鲁棒性。
5. 检索只有字符重叠，不保证召回所有冲突；资料外问题可能命中无关常用词。没有测量真实企业资料库表现。
6. 模型网络不可用由可控替身检查错误传播；不是实际断开模型服务后的在线实验。Mock 只证明流程。
7. 资料、问题和提示都在开发阶段可见；本轮属于开发集回归，未作为独立盲测集。不能报告为真实企业问答准确率。
8. 本人独立运行、语义复核、精简复杂行为、最终 Git SHA 和评审访问权限核对仍为后续工作。

## 自然文本冲突与明确替代对照

吴杰在运行前定义预期：A 有冲突待核实；B 应解释新制度已生效且替代旧期限，再给出明确结果。AI 据此执行两份合成资料副本，原资料和提示词保持不变。

| 场景 | 资料差异 | 实际结果 |
| --- | --- | --- |
| [A 自然冲突](../examples/scenario-validation/natural-conflict/20261030T195249Z_be231d7e/output.json) | 去掉“未注明优先级”等提示，同范围正文分别为 7 日和 14 日 | needs_clarification；引用双方，不能仅凭新日期选择 |
| [B 明确替代](../examples/scenario-validation/explicit-replacement/20261030T195249Z_306c1eae/output.json) | 在 A 基础上仅增加新文件已生效并替代旧期限的 p2 | answered；给出 14 日，并引用 MEAL-B 的 p1 和 p2 |

两次请求问题相同，源码摘要和请求模型配置一致，资料摘要不同。当前观察支持模型根据替代条款改变结论，不能外推为对所有制度冲突可靠。

A 有 2 次无效段落读取，B 有 1 次，模型均收到真实错误后修正；这是过程中的实际失败和效率问题，已保留在 Trace，随后按下述实验改进。

## 工具接口改进与回归中发现的问题

[段落编号改进对照](../examples/improvement/paragraph-discovery/comparison.md)保留原工具文件、实际差异及修改前后 Trace。检索结果新增全部可读段落编号；无效读取也返回正确编号，且仍不授权引用；工具描述同步说明编号选择约束。

在系统提示、资料、输入、模型请求配置及上限不变的工具接口对照中：自然冲突用例无效读取从 2 次降为 0、工具调用从 6 次降为 4；明确替代用例无效读取从 1 次降为 0、工具调用从 5 次降为 4。结论和引用仍符合预期。各版本每个场景一次，不证明统计稳定性或成本收益；字段、错误反馈及工具描述同时改变，不能分别归因。

该工具变更版本的全量回归自动断言为 13/14。[missing-scope 的失败输出](../examples/improvement/paragraph-discovery/after/20261030T195635Z_aa3ab217/missing-scope/output.json)列出 20 日与 45 日条件，却将“我的差旅报销期限”标为 answered、gaps 为空。不能据此证明接口改动导致了语义退化，但该观察明确违反个人适用问题的状态预期，因此保留并修复。

随后在系统提示中加入通用原则：个人适用结论缺少必要条件时须追问，规则概览则可直接列出分支。没有按特定关键词硬编码业务动作。新增 policy-overview 作为反向测试，防止把所有制度比较都变成追问。

针对性两项测试均通过；最新完整 15 项回归也通过自动断言。最终版本的 [missing-scope](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/missing-scope/output.json)返回 needs_clarification 并询问差旅类型，[policy-overview](../examples/improvement/scope-clarification/final/20261030T195833Z_23792fba/policy-overview/output.json)返回 answered 并引用两份制度。最终版本的两组自然文本对照均未发生无效段落读取。

这两步改动分开保存：工具接口对照对应 d8674292dc3059824ee219b3b143996f366f4632e43138bc5271c57b9571eb9c，最终提示修正对应 d38f54a089907ebe53bcb3acd47f304ec1058cb9ad18f22c86c501c70c46220a。中间失败没有被最终成功覆盖。

## 复现

工程测试：python scripts/check_tests.py。

真实模型回归：python scripts/evaluate.py --mode real。仅运行选定用例可添加 --cases normal,conflict,user-annual-leave。新运行保存到新目录，历史结果不覆盖。各用例的 expected_status 等设计见 data/eval_cases.json。

新增配对用例：python scripts/evaluate.py --mode real --cases natural-conflict,explicit-replacement。仅检查已保存对照、无需 API：python scripts/check_scenario_runs.py。资料副本可用 python scripts/prepare_scenarios.py 重建。

检查保留的工具接口改进对照：python scripts/compare_paragraph_discovery.py。最新输入与预期清单共 15 项，完整执行仍为 python scripts/evaluate.py --mode real。
