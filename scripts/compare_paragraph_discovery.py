"""Compare retained paired traces before/after the tool-interface change."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(trace):
    calls = [call for step in trace["steps"] for call in step.get("tools", [])]
    invalid = sum(call["name"] == "read_document" and
                  call["observation"].get("error", {}).get("message") == "Unknown paragraph_id"
                  for call in calls)
    return {"status": trace["result"]["status"], "invalid_paragraph_reads": invalid,
            "tool_calls": trace["tool_calls"], "model_calls": trace["model_calls"],
            "elapsed_seconds": trace["elapsed_seconds"],
            "prompt_tokens": sum(step.get("usage", {}).get("prompt_tokens", 0) for step in trace["steps"]),
            "completion_tokens": sum(step.get("usage", {}).get("completion_tokens", 0) for step in trace["steps"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after", type=Path, help="A completed evaluate.py output directory")
    args = parser.parse_args()
    directory = ROOT / "examples" / "improvement" / "paragraph-discovery"
    if args.after:
        after = args.after
    else:
        candidates = sorted((directory / "after").glob("*/summary.json"))
        if not candidates:
            parser.error("No after evaluation available")
        after = candidates[-1].parent
    summary = read_json(after / "summary.json")
    baseline = ROOT / "examples" / "scenario-validation"
    baseline_summary = read_json(baseline / "summary.json")
    rows = []
    for case_id in ("natural-conflict", "explicit-replacement"):
        before_row = next(row for row in baseline_summary["cases"] if row["case_id"] == case_id)
        before_path = baseline / before_row["trace_path"]
        after_path = after / case_id / "trace.json"
        before_trace, after_trace = read_json(before_path), read_json(after_path)
        after_row = next(row for row in summary["cases"] if row["case_id"] == case_id)
        controls = {"same_input": before_trace["input"] == after_trace["input"],
                    "same_corpus": before_trace["corpus_sha256"] == after_trace["corpus_sha256"],
                    "same_requested_model": before_trace["requested_model"] == after_trace["requested_model"],
                    "same_limits": before_trace["limits"] == after_trace["limits"],
                    "real_model": before_trace["mode"] == after_trace["mode"] == "real",
                    "source_changed": before_trace["source_sha256"] != after_trace["source_sha256"]}
        rows.append({"case_id": case_id, "before": metrics(before_trace), "after": metrics(after_trace),
                     "controls": controls, "after_automatic_checks_passed": after_row["automatic_checks_passed"],
                     "before_trace": os.path.relpath(before_path, directory).replace("\\", "/"),
                     "after_trace": os.path.relpath(after_path, directory).replace("\\", "/"),
                     "before_source_sha256": before_trace["source_sha256"],
                     "after_source_sha256": after_trace["source_sha256"]})
    original = (directory / "before-tools.py.txt").read_text(encoding="utf-8")
    current = (ROOT / "src" / "knowledge_agent" / "tools.py").read_text(encoding="utf-8")
    patch = "".join(difflib.unified_diff(original.splitlines(keepends=True), current.splitlines(keepends=True),
                                       fromfile="before/tools.py", tofile="after/tools.py"))
    (directory / "tools.patch").write_text(patch, encoding="utf-8")
    report = {"cases": rows, "after_full_suite_count": len(summary["cases"]),
              "after_full_suite_automatic_passed": sum(row["automatic_checks_passed"] for row in summary["cases"]),
              "before_tools_sha256": hashlib.sha256((directory / "before-tools.py.txt").read_bytes()).hexdigest(),
              "scope": "Exploratory single-run comparison per scenario, not statistical or cost evidence. Tool metadata, error feedback and tool descriptions changed together."}
    (directory / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 可读段落编号改进对照", "", "同一输入、同一资料、同一请求模型与调用上限；保留修改前后实际 Trace。", "",
             "| 场景 | 无效段落读取 前→后 | 工具调用 前→后 | 模型调用 前→后 | 最终状态 前→后 |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        a, b = row["before"], row["after"]
        lines.append("| {case} | {ai}→{bi} | {at}→{bt} | {am}→{bm} | {ast}→{bst} |".format(
            case=row["case_id"], ai=a["invalid_paragraph_reads"], bi=b["invalid_paragraph_reads"],
            at=a["tool_calls"], bt=b["tool_calls"], am=a["model_calls"], bm=b["model_calls"],
            ast=a["status"], bst=b["status"]))
    lines += ["", "## 变更与验证", "", "检索返回全部可读段落编号；无效读取也返回正确编号，但不授权引用。工具描述说明只从已给编号中选择。系统提示、检索排序、合成资料和调用上限未调整。", "",
              "这些接口变更同时发生，不能将观察到的变化单独归因于某一字段。每个场景每个版本一次运行，未证明稳定性或成本节省。", "",
              "该工具变更版本的完整回归自动断言为 {}/{}；配对场景正确不代表所有场景均通过。完整结果见 comparison.json，失败记录保留在 after 目录。".format(report["after_full_suite_automatic_passed"], report["after_full_suite_count"]), "",
              "编号是导航元数据；只有成功读取原文才进入证据集合。即使已知编号，未读取也不能引用。", ""]
    for row in rows:
        lines.append("- " + row["case_id"] + "：[修改前 Trace](" + row["before_trace"] + ")，[修改后 Trace](" + row["after_trace"] + ")。")
    (directory / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(all(row["controls"].values()) and row["after_automatic_checks_passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
