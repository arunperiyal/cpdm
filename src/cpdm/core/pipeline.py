"""Reproducible, declarative preparation pipelines."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd

from cpdm.core import contracts
from cpdm.core.scoring import ScoringEngine


PIPELINE_VERSION = 1
OPERATIONS = {"validate", "rename_headers", "replace_values", "score", "compute"}
FUNCTIONS = {"mean", "sum", "min", "max", "std"}


def _fingerprint(frame):
    payload = pd.util.hash_pandas_object(frame, index=True).values.tobytes()
    columns = json.dumps([str(column) for column in frame.columns]).encode("utf-8")
    return hashlib.sha256(columns + payload).hexdigest()


def _definition_fingerprint(definition):
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_definition(definition):
    if not isinstance(definition, dict):
        raise contracts.ContractError("Pipeline definition must be a JSON object.")
    if definition.get("version", PIPELINE_VERSION) != PIPELINE_VERSION:
        raise contracts.ContractError(
            f"Unsupported pipeline version: {definition.get('version')}"
        )
    steps = definition.get("steps")
    if not isinstance(steps, list) or not steps:
        raise contracts.ContractError("Pipeline definition needs a non-empty 'steps' list.")
    for position, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise contracts.ContractError(f"Pipeline step {position} is not an object.")
        operation = step.get("op")
        if operation not in OPERATIONS:
            raise contracts.ContractError(
                f"Pipeline step {position} has unknown operation '{operation}'."
            )
    return definition


@dataclass
class PipelineResult:
    """The prepared dataframe and its reproducibility manifest."""

    frame: pd.DataFrame
    manifest: dict
    dry_run: bool = False

    def as_dict(self):
        return {
            "dry_run": self.dry_run,
            "manifest": self.manifest,
            "rows": len(self.frame),
            "columns": list(self.frame.columns),
        }


class PreparationPipeline:
    """Run a validated list of preparation operations on a dataframe copy."""

    def __init__(self, definition):
        self.definition = _read_definition(definition)

    @classmethod
    def from_json(cls, payload):
        if isinstance(payload, str):
            payload = json.loads(payload)
        return cls(payload)

    def _rename_headers(self, frame, step):
        mapping = step.get("map", {})
        if not isinstance(mapping, dict):
            raise contracts.ContractError("rename_headers 'map' must be an object.")
        unknown = sorted(set(mapping) - set(frame.columns))
        if unknown:
            raise contracts.ContractError(
                "rename_headers references unknown columns: " + ", ".join(unknown)
            )
        renamed = frame.rename(columns=mapping)
        warnings = contracts.validate_dataframe(renamed)
        return renamed, {"columns_changed": sum(
            old != mapping.get(old, old) for old in frame.columns
        ), "warnings": warnings}

    def _replace_values(self, frame, step):
        mapping = step.get("map", {})
        if not isinstance(mapping, dict):
            raise contracts.ContractError("replace_values 'map' must be an object.")
        selected = step.get("columns")
        columns = list(frame.columns) if selected is None else list(selected)
        unknown = sorted(set(columns) - set(frame.columns))
        if unknown:
            raise contracts.ContractError(
                "replace_values references unknown columns: " + ", ".join(unknown)
            )

        changed_cells = 0
        for column in columns:
            if pd.api.types.is_numeric_dtype(frame[column]):
                continue
            series = frame[column]
            present = series.notna()
            text = series[present].astype(str)
            updated = text.copy()
            for old, new in sorted(mapping.items(), key=lambda item: len(str(item[0])), reverse=True):
                updated = updated.str.replace(str(old), str(new), regex=False)
            changed_cells += int((updated != text).sum())
            frame.loc[present, column] = updated
        return frame, {"cells_changed": changed_cells}

    def _compute(self, frame, step):
        name = str(step.get("new_col_name", "")).strip()
        function = step.get("function", "mean")
        columns = step.get("columns", [])
        if not name:
            raise contracts.ContractError("compute requires new_col_name.")
        if function not in FUNCTIONS:
            raise contracts.ContractError(
                f"Unsupported compute function '{function}'."
            )
        if not columns:
            raise contracts.ContractError("compute requires at least one column.")
        unknown = sorted(set(columns) - set(frame.columns))
        if unknown:
            raise contracts.ContractError(
                "compute references unknown columns: " + ", ".join(unknown)
            )
        numeric = frame[columns].apply(pd.to_numeric, errors="coerce")
        frame[name] = getattr(numeric, function)(axis=1)
        return frame, {"new_column": name, "function": function}

    def run(self, frame, source_filename="dataset", context=None, dry_run=False):
        contracts.validate_dataframe(frame)
        context = context or {}
        working = frame.copy(deep=True)
        manifest = {
            "kind": "cpdm-preparation-run",
            "version": PIPELINE_VERSION,
            "source_filename": source_filename,
            "source_fingerprint": _fingerprint(frame),
            "definition_fingerprint": _definition_fingerprint(self.definition),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "steps": [],
            "warnings": [],
            "artifacts": [],
        }

        for position, step in enumerate(self.definition["steps"], start=1):
            operation = step["op"]
            before = _fingerprint(working)
            if operation == "validate":
                details = {"warnings": contracts.validate_dataframe(working)}
            elif operation == "rename_headers":
                working, details = self._rename_headers(working, step)
            elif operation == "replace_values":
                working, details = self._replace_values(working, step)
            elif operation == "compute":
                working, details = self._compute(working, step)
            elif operation == "score":
                scale_map = context.get("scale_map")
                if scale_map is None:
                    raise contracts.ContractError(
                        "score requires a ScaleMap in the pipeline context."
                    )
                working, report = ScoringEngine().score(
                    working, scale_map, step.get("scale")
                )
                details = report.as_dict()
            else:  # pragma: no cover - guarded by _read_definition
                raise contracts.ContractError(f"Unknown pipeline operation '{operation}'.")

            step_report = {
                "position": position,
                "op": operation,
                "config": {key: value for key, value in step.items() if key != "op"},
                "changed": before != _fingerprint(working),
                "details": details,
            }
            manifest["steps"].append(step_report)
            manifest["warnings"].extend(details.get("warnings", []))

        manifest["output_fingerprint"] = _fingerprint(working)
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        return PipelineResult(working, manifest, dry_run=dry_run)
