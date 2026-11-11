"""Check that roadmap and architecture documentation remain internally linked."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "PLAN.md"


def main():
    text = PLAN.read_text(encoding="utf-8")
    required = ("Stage 11", "Stage 12", "Stage 13", "Stage 14", "Stage 15", "Stage 16")
    missing = [heading for heading in required if heading not in text]
    if missing:
        raise SystemExit("Missing roadmap headings: " + ", ".join(missing))
    for relative in re.findall(r"`(docs/architecture/[^`]+\.md)`", text):
        if not (ROOT / relative).exists():
            raise SystemExit(f"Missing architecture document: {relative}")
    print("Documentation consistency checks passed.")


if __name__ == "__main__":
    main()
