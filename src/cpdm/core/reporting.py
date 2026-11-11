"""Research report bundles, figure specifications, and run comparisons."""

from dataclasses import dataclass, field
import json
from pathlib import Path

import pandas as pd

from cpdm.core.analysis import AnalysisResult, ReportWriter
from cpdm.core.contracts import ContractError
from cpdm.core.governance import ExportPolicy


@dataclass(frozen=True)
class PrivacyPolicy:
    """Controls identifier, free-text, and intermediate export columns."""

    drop_columns: tuple[str, ...] = ()
    redact_columns: tuple[str, ...] = ()
    replacement: str = "[REDACTED]"

    def apply(self, frame):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Privacy filtering requires a pandas DataFrame.")
        result = frame.drop(columns=list(self.drop_columns), errors="ignore").copy()
        for column in self.redact_columns:
            if column in result:
                result[column] = self.replacement
        return result

    def as_export_policy(self):
        """Return the field-level policy equivalent of this legacy helper."""
        from cpdm.core.governance import FieldClassification

        return ExportPolicy(
            fields=tuple(
                FieldClassification(column, "restricted", "drop")
                for column in self.drop_columns
            ) + tuple(
                FieldClassification(column, "restricted", "redact")
                for column in self.redact_columns
            ),
            replacement=self.replacement,
        )


@dataclass(frozen=True)
class FigureSpec:
    """Portable description of a figure and its exported data."""

    name: str
    kind: str
    data_columns: tuple[str, ...] = ()
    title: str = ""
    options: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "data_columns": list(self.data_columns),
            "title": self.title,
            "options": dict(self.options),
        }


class ReportBundle:
    """Write all inputs and outputs needed to inspect a research run."""

    def __init__(self, path):
        self.path = Path(path)

    def write(
        self,
        *,
        definitions=None,
        preparation_manifest=None,
        analysis_result: AnalysisResult | None = None,
        figures=(),
        figure_data=None,
        warnings=(),
        privacy_policy=None,
    ):
        self.path.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "cpdm-report-bundle",
            "version": 1,
            "warnings": list(warnings),
            "figures": [figure.as_dict() for figure in figures],
        }
        if definitions is not None:
            payload["definitions"] = definitions
            (self.path / "definitions.json").write_text(
                json.dumps(definitions, indent=2, sort_keys=True), encoding="utf-8"
            )
        if preparation_manifest is not None:
            payload["preparation_manifest"] = preparation_manifest
            (self.path / "preparation_manifest.json").write_text(
                json.dumps(preparation_manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        if analysis_result is not None:
            payload["analysis"] = analysis_result.as_dict()
            ReportWriter.write_json(analysis_result, self.path / "analysis.json")
            ReportWriter.write_csv(analysis_result, self.path / "estimates.csv")
        if figure_data:
            for name, frame in figure_data.items():
                if not isinstance(frame, pd.DataFrame):
                    raise ContractError(f"Figure data '{name}' must be a DataFrame.")
                if privacy_policy:
                    frame = privacy_policy.apply(frame)
                frame.to_csv(self.path / f"{name}.csv", index=False)
        (self.path / "bundle.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        return self.path


def compare_result_tables(left, right, labels=("left", "right")):
    """Compare two result tables by stable path and role identifiers."""
    if not isinstance(left, pd.DataFrame) or not isinstance(right, pd.DataFrame):
        raise ContractError("Result comparisons require pandas DataFrames.")
    keys = ["path", "role"]
    missing = [key for key in keys if key not in left or key not in right]
    if missing:
        raise ContractError("Result tables need columns: " + ", ".join(missing))
    estimate_column = "estimate"
    if estimate_column not in left or estimate_column not in right:
        raise ContractError("Result tables need an estimate column.")
    joined = left[keys + [estimate_column]].merge(
        right[keys + [estimate_column]],
        on=keys,
        how="outer",
        suffixes=(f"_{labels[0]}", f"_{labels[1]}"),
        indicator=True,
    )
    joined["estimate_difference"] = (
        joined[f"estimate_{labels[1]}"] - joined[f"estimate_{labels[0]}"]
    )
    return joined.sort_values(keys).reset_index(drop=True)
