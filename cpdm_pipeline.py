#!/usr/bin/env python3
"""Run a saved CPDM preparation pipeline without opening the web workspace."""

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from cpdm.core.measurement import ScaleMap  # noqa: E402
from cpdm.core.pipeline import PreparationPipeline  # noqa: E402


def read_table(path):
    extension = os.path.splitext(path)[1].lower()
    if extension in (".xlsx", ".xlsm"):
        return pd.read_excel(path)
    if extension == ".tsv":
        return pd.read_csv(path, sep="\t")
    return pd.read_csv(path)


def write_table(frame, path):
    extension = os.path.splitext(path)[1].lower()
    if extension in (".xlsx", ".xlsm"):
        frame.to_excel(path, index=False, sheet_name="Processed_Data")
    else:
        frame.to_csv(path, index=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source CSV, TSV, or XLSX file.")
    parser.add_argument("--pipeline", required=True, help="Pipeline JSON definition.")
    parser.add_argument("--output", help="Output CSV or XLSX path.")
    parser.add_argument("--manifest", help="Manifest JSON path.")
    parser.add_argument("--scale-map", help="CSV scale map for score steps.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview only.")
    args = parser.parse_args(argv)

    with open(args.pipeline, encoding="utf-8") as handle:
        definition = json.load(handle)
    frame = read_table(args.input)
    context = {}
    if args.scale_map:
        context["scale_map"] = ScaleMap.from_csv(args.scale_map)

    result = PreparationPipeline(definition).run(
        frame,
        source_filename=os.path.basename(args.input),
        context=context,
        dry_run=args.dry_run,
    )
    if args.output and not args.dry_run:
        result.manifest["artifacts"].append({"kind": "table", "path": args.output})
    manifest = json.dumps(result.manifest, indent=2, ensure_ascii=False)
    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as handle:
            handle.write(manifest + "\n")
    if args.dry_run:
        print(manifest)
        return 0
    if not args.output:
        parser.error("--output is required unless --dry-run is used")
    write_table(result.frame, args.output)
    if not args.manifest:
        print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
