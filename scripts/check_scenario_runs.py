"""Check saved paired real-model runs without making API requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import check

cases = {case["id"]: case for case in json.loads((ROOT / "data" / "eval_cases.json").read_text(encoding="utf-8"))}
directory = ROOT / "examples" / "scenario-validation"
rows = []
traces = []
for case_id in ("natural-conflict", "explicit-replacement"):
    candidates = sorted((directory / case_id).glob("*/trace.json"))
    if not candidates:
        raise SystemExit("Missing run for " + case_id)
    path = candidates[-1]
    trace = json.loads(path.read_text(encoding="utf-8"))
    traces.append(trace)
    assertions = check(cases[case_id], trace["result"], trace)
    assertions["real_model"] = trace["mode"] == "real"
    assertions["expected_input"] = trace["input"]["question"] == cases[case_id]["question"]
    rows.append({"case_id": case_id, "trace_path": str(path.relative_to(directory)).replace("\\", "/"),
                 "status": trace["result"]["status"], "model_calls": trace["model_calls"],
                 "tool_calls": trace["tool_calls"], "checks": assertions,
                 "automatic_checks_passed": all(assertions.values()),
                 "source_sha256": trace["source_sha256"], "corpus_sha256": trace["corpus_sha256"]})
pair_checks = {"same_question": traces[0]["input"] == traces[1]["input"],
               "same_source": traces[0]["source_sha256"] == traces[1]["source_sha256"],
               "same_model_config": traces[0]["requested_model"] == traces[1]["requested_model"],
               "different_corpus": traces[0]["corpus_sha256"] != traces[1]["corpus_sha256"]}
report = {"checked_at": datetime.now(timezone.utc).isoformat(), "cases": rows,
          "pair_checks": pair_checks, "scope": "Automatic checks over retained real-model traces; one run per scenario"}
(directory / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(pair_checks.values()) and all(row["automatic_checks_passed"] for row in rows) else 1)
