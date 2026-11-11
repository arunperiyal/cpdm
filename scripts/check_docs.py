"""Check that roadmap and architecture documentation remain internally linked."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "PLAN.md"
sys.path.insert(0, str(ROOT / "src"))

from cpdm.core.document_schemas import SCHEMAS  # noqa: E402


def main():
    text = PLAN.read_text(encoding="utf-8")
    required = ("Stage 11", "Stage 12", "Stage 13", "Stage 14", "Stage 15", "Stage 16")
    missing = [heading for heading in required if heading not in text]
    if missing:
        raise SystemExit("Missing roadmap headings: " + ", ".join(missing))
    for relative in re.findall(r"`(docs/architecture/[^`]+\.md)`", text):
        if not (ROOT / relative).exists():
            raise SystemExit(f"Missing architecture document: {relative}")
    schema_doc = (ROOT / "docs/architecture/SCHEMAS.md").read_text(encoding="utf-8")
    for kind, schema in SCHEMAS.items():
        if f"| {kind} | {schema.version} |" not in schema_doc:
            raise SystemExit(f"Schema documentation is missing '{kind}'.")
    print("Documentation consistency checks passed.")


if __name__ == "__main__":
    main()
