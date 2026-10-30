"""Run deterministic tests and retain their actual output."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from knowledge_agent.agent import source_digest

suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
directory = ROOT / "examples" / "test-results"
directory.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
report = {"timestamp": datetime.now(timezone.utc).isoformat(), "python": sys.version,
          "source_sha256": source_digest(), "tests_run": result.testsRun,
          "failures": len(result.failures), "errors": len(result.errors),
          "scope": "Deterministic tests with scripted model doubles; not real-model decision evaluation"}
(directory / (stamp + ".txt")).write_text(stream.getvalue(), encoding="utf-8")
(directory / (stamp + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(stream.getvalue())
raise SystemExit(0 if result.wasSuccessful() else 1)
