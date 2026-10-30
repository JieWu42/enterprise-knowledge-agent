"""Local CLI entry point; no editable installation required."""
from pathlib import Path
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from knowledge_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
