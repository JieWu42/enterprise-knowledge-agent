# 提交与快速复现

选题：第 3 题，企业知识问答 Agent。

仓库：https://github.com/JieWu42/enterprise-knowledge-agent 。仓库公开可读，默认分支 main。

实际投入约 2.5 小时。最终 commit SHA 以提交时固定的版本为准，在仓库目录执行 git rev-parse HEAD 获取；SHA 不写入同一提交的内容，避免自引用。

## 快速验证

Python 3.9 或以上，无第三方运行依赖。

```powershell
git clone https://github.com/JieWu42/enterprise-knowledge-agent.git
cd enterprise-knowledge-agent
git rev-parse HEAD
python -m unittest discover -s tests -v
python run.py --mode mock --question "境内差旅报销期限？"
```

离线 Mock 会返回 incomplete/mock_only，退出码为 2，这是固定演示流程的预期结果，不验证真实模型决策效果。

真实模型需要配置 DEEPSEEK_API_KEY；环境变量模板及完整命令见 README.md。已保留的真实模型记录无需密钥即可阅读。

## 评审建议阅读顺序

1. README.md 和 docs/01-requirements.md：用户、范围、运行入口。
2. docs/02-solution.md 与 src/knowledge_agent/agent.py：模型选择动作、工具观察和结束条件。
3. docs/03-evaluation.md：21 项工程测试、最新 15 项真实模型用例的自动断言、原始失败及限制。
4. examples/personal-validation/review.md：本人独立运行与验收。
5. docs/04-ai-usage.md、docs/05-retrospective.md、docs/06-contribution-log.md：AI 范围、实际收获和个人贡献。

正式提交时填写题号、仓库 URL 和最终完整 commit SHA。项目代码与验证材料已公开，不在本仓库复制完整考试题面；本文件不代表已在考试平台交卷。
