# 可读段落编号改进对照

同一输入、同一资料、同一请求模型与调用上限；保留修改前后实际 Trace。

| 场景 | 无效段落读取 前→后 | 工具调用 前→后 | 模型调用 前→后 | 最终状态 前→后 |
| --- | --- | --- | --- | --- |
| natural-conflict | 2→0 | 6→4 | 4→3 | needs_clarification→needs_clarification |
| explicit-replacement | 1→0 | 5→4 | 4→3 | answered→answered |

## 变更与验证

检索返回全部可读段落编号；无效读取也返回正确编号，但不授权引用。工具描述说明只从已给编号中选择。系统提示、检索排序、合成资料和调用上限未调整。

这些接口变更同时发生，不能将观察到的变化单独归因于某一字段。每个场景每个版本一次运行，未证明稳定性或成本节省。

该工具变更版本的完整回归自动断言为 13/14；配对场景正确不代表所有场景均通过。完整结果见 comparison.json，失败记录保留在 after 目录。

编号是导航元数据；只有成功读取原文才进入证据集合。即使已知编号，未读取也不能引用。

- natural-conflict：[修改前 Trace](../../scenario-validation/natural-conflict/20261030T195249Z_be231d7e/trace.json)，[修改后 Trace](after/20261030T195635Z_aa3ab217/natural-conflict/trace.json)。
- explicit-replacement：[修改前 Trace](../../scenario-validation/explicit-replacement/20261030T195249Z_306c1eae/trace.json)，[修改后 Trace](after/20261030T195635Z_aa3ab217/explicit-replacement/trace.json)。
