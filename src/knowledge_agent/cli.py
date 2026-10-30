import argparse
import json
import sys
from pathlib import Path

from .agent import Agent
from .models import ChatModel, ModelError, OfflineMock
from .tools import DocumentStore, ToolExecutor

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence-grounded enterprise knowledge CLI")
    parser.add_argument("--mode", choices=["real", "mock"], default="real")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--question")
    inputs.add_argument("--input", type=Path, help="JSON with question and optional history")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "documents.json")
    parser.add_argument("--no-query-expansion", action="store_true", help="Disable domain aliases for retrieval ablation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--max-model-calls", type=int, default=8)
    parser.add_argument("--max-tool-calls", type=int, default=10)
    parser.add_argument("--model-timeout", type=float, default=60)
    parser.add_argument("--fail-tool", choices=["search_documents", "read_document"])
    parser.add_argument("--fail-count", type=int, default=0, help="-1 for persistent failure; otherwise nonnegative")
    args = parser.parse_args(argv)
    try:
        if args.fail_count < -1 or (args.fail_count and not args.fail_tool) or args.model_timeout <= 0:
            raise ValueError("Invalid failure injection or timeout configuration")
        payload = json.loads(args.input.read_text(encoding="utf-8-sig")) if args.input else {"question": args.question}
        store = DocumentStore(args.data, expand_query=not args.no_query_expansion)
        executor = ToolExecutor(store, args.fail_tool, args.fail_count)
        model = OfflineMock() if args.mode == "mock" else ChatModel(args.model_timeout)
        agent = Agent(model, executor, args.max_model_calls, args.max_tool_calls)
        result, trace = agent.run(payload["question"], payload.get("history"))
        destination = args.output_dir / trace["trace_id"]
        destination.mkdir(parents=True, exist_ok=False)
        for name, content in (("input.json", trace["input"]), ("output.json", result), ("trace.json", trace)):
            (destination / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("Run records: " + str(destination.resolve()), file=sys.stderr)
        return 0 if result["status"] == "answered" else 2
    except (OSError, ValueError, KeyError, TypeError, ModelError) as exc:
        print(json.dumps({"status": "incomplete", "reason_code": "configuration_error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
