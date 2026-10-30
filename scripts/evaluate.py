"""Reproducible real-model checks. Automatic checks are not semantic grading."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
from knowledge_agent.agent import Agent, source_digest
from knowledge_agent.models import ChatModel, OfflineMock
from knowledge_agent.tools import DocumentStore, ToolExecutor


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check(case, result, trace):
    assertions = {"status": result["status"] in case["expected_status"]}
    ids = {c["document_id"] for c in result["citations"]}
    for doc in case.get("required_citations", []):
        assertions["citation_" + doc] = doc in ids
    paragraphs = {(c["document_id"], c["paragraph_id"]) for c in result["citations"]}
    for doc, paragraph in case.get("required_citation_paragraphs", []):
        assertions["citation_" + doc + "_" + paragraph] = (doc, paragraph) in paragraphs
    for term in case.get("required_answer_terms", []):
        assertions["contains_" + term] = term in result["answer"]
    for term in case.get("forbidden_answer_terms", []):
        assertions["excludes_" + term] = term not in result["answer"]
    if case.get("require_gap"):
        assertions["gap"] = bool(result["gaps"])
    if case.get("forbid_answered"):
        assertions["not_answered"] = result["status"] not in ("answered", "partially_answered")
    if case.get("expected_reason"):
        assertions["reason_code"] = result["reason_code"] == case["expected_reason"]
    tools = [t for step in trace["steps"] for t in step.get("tools", [])]
    if case.get("expect_tool_failure"):
        assertions["observed_tool_failure"] = any(not t["observation"].get("ok") for t in tools)
    assertions["within_model_limit"] = trace["model_calls"] <= trace["limits"]["model_calls"]
    assertions["within_tool_limit"] = trace["tool_calls"] <= trace["limits"]["tool_calls"]
    if case["id"] == "out-of-scope":
        assertions["no_unsupported_citation"] = not result["citations"]
    return assertions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--cases", help="Comma-separated case IDs; omitted means all")
    parser.add_argument("--no-query-expansion", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "examples" / "evaluation")
    args = parser.parse_args()
    cases = json.loads((ROOT / "data" / "eval_cases.json").read_text(encoding="utf-8"))
    if args.cases:
        selected = set(args.cases.split(","))
        unknown = selected - {c["id"] for c in cases}
        if unknown:
            parser.error("Unknown case IDs: " + ",".join(sorted(unknown)))
        cases = [c for c in cases if c["id"] in selected]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    destination = args.output_dir / stamp
    destination.mkdir(parents=True, exist_ok=False)
    model = ChatModel() if args.mode == "real" else OfflineMock()
    rows = []
    for case in cases:
        directory = destination / case["id"]
        directory.mkdir()
        corpus = ROOT / case.get("data_path", "data/documents.json")
        if case.get("mutation"):
            documents = json.loads(corpus.read_text(encoding="utf-8"))
            mutation = case["mutation"]
            target = next(d for d in documents if d["id"] == mutation["document_id"])
            paragraph = next(p for p in target["paragraphs"] if p["id"] == mutation["paragraph_id"])
            if mutation["old"] not in paragraph["text"]:
                raise ValueError("Mutation target missing")
            paragraph["text"] = paragraph["text"].replace(mutation["old"], mutation["new"])
            corpus = directory / "documents.json"
            dump(corpus, documents)
        store = DocumentStore(corpus, expand_query=not args.no_query_expansion)
        executor = ToolExecutor(store, case.get("fail_tool"), case.get("fail_count", 0))
        agent = Agent(model, executor, case.get("max_model_calls", 8), case.get("max_tool_calls", 10))
        result, trace = agent.run(case["question"], case.get("history", []))
        assertions = check(case, result, trace) if args.mode == "real" else {"mock_labeled": result["reason_code"] == "mock_only" or result["reason_code"] == "step_limit"}
        row = {"case_id": case["id"], "status": result["status"], "reason_code": result["reason_code"],
               "checks": assertions, "automatic_checks_passed": all(assertions.values()),
               "model_calls": trace["model_calls"], "tool_calls": trace["tool_calls"],
               "seconds": trace["elapsed_seconds"], "trace_path": case["id"] + "/trace.json"}
        rows.append(row)
        for name, payload in (("input.json", trace["input"]), ("output.json", result),
                              ("trace.json", trace), ("expectation.json", case), ("checks.json", row)):
            dump(directory / name, payload)
        print(case["id"] + ": " + result["status"] + " | checks=" + str(row["automatic_checks_passed"]), flush=True)
        dump(destination / "summary.json", {"mode": args.mode, "source_sha256": source_digest(), "cases": rows,
                                            "scope": "Automatic assertions only; manual semantic review required"})
    print("Evaluation records: " + str(destination.resolve()), flush=True)
    return 0 if all(row["automatic_checks_passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
