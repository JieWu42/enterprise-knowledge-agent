"""Deterministic retrieval ablation over a small, visible development set."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
from knowledge_agent.agent import source_digest
from knowledge_agent.tools import DocumentStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="baseline,expanded")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "examples" / "retrieval-improvement" / "comparison")
    args = parser.parse_args()
    variants = args.variants.split(",")
    if not variants or any(v not in ("baseline", "expanded") for v in variants):
        parser.error("variants must be baseline and/or expanded")
    path = ROOT / "data" / "retrieval_eval.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    destination = args.output_dir / stamp
    destination.mkdir(parents=True, exist_ok=False)
    summary = {"source_sha256": source_digest(), "queries_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "query_count": len(cases), "scope": "Visible synthetic development set; dictionary-assisted query expansion; not held-out or end-to-end QA accuracy", "variants": {}}
    for variant in variants:
        store = DocumentStore(ROOT / "data" / "documents.json")
        if hasattr(store, "expand_query"):
            store.expand_query = variant == "expanded"
        elif variant == "expanded":
            parser.error("This source version does not support query expansion")
        rows = []
        for case in cases:
            gold = set(case["relevant_documents"])
            if not gold or not gold.issubset(store.docs):
                raise ValueError("Invalid relevant document IDs")
            response = store.search(case["query"], top_k=8)
            ranked = [hit["document_id"] for hit in response["results"]]
            first_rank = next((index for index, doc in enumerate(ranked, 1) if doc in gold), None)
            rows.append({**case, "ranked_documents": ranked, "hit_at_1": bool(ranked and ranked[0] in gold),
                         "recall_at_3": len(set(ranked[:3]) & gold) / len(gold),
                         "reciprocal_rank": 1 / first_rank if first_rank else 0,
                         "applied_aliases": response.get("applied_aliases", [])})
        metrics = {"hit_at_1": sum(row["hit_at_1"] for row in rows) / len(rows),
                   "macro_recall_at_3": sum(row["recall_at_3"] for row in rows) / len(rows),
                   "mrr_at_8": sum(row["reciprocal_rank"] for row in rows) / len(rows)}
        payload = {"variant": variant, "corpus_sha256": store.sha256,
                   "retrieval_config": getattr(store, "retrieval_config", {"expand_query": False}),
                   "metrics": metrics, "cases": rows}
        (destination / (variant + ".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["variants"][variant] = metrics
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
