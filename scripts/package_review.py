"""Create a review archive and verify it in a fresh directory without model keys."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT.parent / "output" / "submission"
DESTINATION.mkdir(parents=True, exist_ok=True)
archive = DESTINATION / "enterprise-knowledge-agent-review.zip"
excluded_parts = {".git", ".venv", "__pycache__", ".pytest_cache", "runs"}
files = [path for path in ROOT.rglob("*") if path.is_file()
         and not any(part in excluded_parts or part.endswith(".egg-info") for part in path.relative_to(ROOT).parts)
         and not path.name.endswith(".pyc")
         and not (path.name.startswith(".env") and path.name != ".env.example")]
keys = [value.encode() for name, value in os.environ.items() if name.endswith("API_KEY") and len(value) > 12]
if any(key in path.read_bytes() for path in files for key in keys):
    raise SystemExit("Configured credential found in review files; archive not created")
with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
    for path in sorted(files):
        bundle.write(path, "enterprise-knowledge-agent/" + path.relative_to(ROOT).as_posix())

environment = {name: value for name, value in os.environ.items()
               if not name.startswith(("DEEPSEEK_", "OPENAI_"))}
environment["PYTHONIOENCODING"] = "utf-8"
with tempfile.TemporaryDirectory(prefix="knowledge-agent-review-") as folder:
    with ZipFile(archive) as bundle:
        bundle.extractall(folder)
    extracted = Path(folder) / "enterprise-knowledge-agent"
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                           cwd=extracted, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
    mock = subprocess.run([sys.executable, "run.py", "--mode", "mock", "--question", "境内差旅报销期限？"],
                          cwd=extracted, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
    try:
        mock_output = json.loads(mock.stdout)
    except ValueError:
        mock_output = {}
    passed = tests.returncode == 0 and mock.returncode == 2 and mock_output.get("reason_code") == "mock_only"

(DESTINATION / "clean-tests.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
(DESTINATION / "clean-mock-output.json").write_text(json.dumps(mock_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report = {"archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
          "file_count": len(files), "archive_bytes": archive.stat().st_size,
          "clean_directory_test_exit": tests.returncode, "offline_cli_exit": mock.returncode,
          "offline_reason": mock_output.get("reason_code"), "smoke_check_passed": passed,
          "scope": "Review archive; original model keys removed from smoke-check environment; no real model calls"}
(DESTINATION / "review-package-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if passed else 1)
