"""Metadata-driven instruments, scoring, and reliability reports.

The measurement layer is deliberately independent of the Flask session and
the interactive scale editor. A scale map can therefore be reviewed, tested,
and reused by batch jobs or future analysis pipelines.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path

import pandas as pd

from cpdm.core.contracts import ContractError


REQUIRED_SCALE_MAP_COLUMNS = (
    "scale",
    "dimension_code",
    "dimension_label",
    "item_number",
    "column_name",
    "reverse",
    "item_min",
    "item_max",
    "is_total",
)


def _as_bool(value, field_name):
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ContractError(f"'{value}' is not a valid {field_name} boolean.")


def _as_optional_float(value, field_name):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ContractError(f"'{value}' is not a valid {field_name}.") from None


@dataclass(frozen=True)
class ItemDefinition:
    """One source item and its scoring metadata."""

    scale: str
    dimension_code: str
    dimension_label: str
    item_number: int
    column_name: str
    reverse: bool = False
    item_min: float | None = None
    item_max: float | None = None
    is_total: bool = False


@dataclass(frozen=True)
class DimensionDefinition:
    """An ordered composite definition."""

    scale: str
    code: str
    label: str
    items: tuple[ItemDefinition, ...]
    is_total: bool = False
    min_valid: int = 1


@dataclass(frozen=True)
class InstrumentDefinition:
    """All dimensions belonging to one named instrument."""

    name: str
    version: str
    dimensions: tuple[DimensionDefinition, ...]

    @classmethod
    def from_scale_map(cls, scale_map, name, version="1"):
        dimensions = tuple(scale_map.dimensions(name))
        if not dimensions:
            raise ContractError(f"No dimensions found for scale '{name}'.")
        return cls(name=name, version=str(version), dimensions=dimensions)

    @property
    def items(self):
        """Unique source items, preserving their first metadata definition."""
        seen = {}
        for dimension in self.dimensions:
            for item in dimension.items:
                seen.setdefault(item.column_name, item)
        return tuple(seen.values())


class ScaleMap:
    """Validated item-to-dimension metadata, compatible with the R CSV shape."""

    def __init__(self, items):
        self.items = tuple(items)
        self._validate()

    @classmethod
    def from_dataframe(cls, frame):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Scale map must be a pandas DataFrame.")
        missing = [column for column in REQUIRED_SCALE_MAP_COLUMNS if column not in frame]
        if missing:
            raise ContractError(
                "Scale map is missing required columns: " + ", ".join(missing)
            )

        items = []
        for position, row in frame.iterrows():
            try:
                item_number = int(row["item_number"])
            except (TypeError, ValueError):
                raise ContractError(
                    f"Scale map row {position + 1} has an invalid item_number."
                ) from None

            values = {
                "scale": str(row["scale"]).strip(),
                "dimension_code": str(row["dimension_code"]).strip(),
                "dimension_label": str(row["dimension_label"]).strip(),
                "item_number": item_number,
                "column_name": str(row["column_name"]).strip(),
                "reverse": _as_bool(row["reverse"], "reverse"),
                "item_min": _as_optional_float(row["item_min"], "item_min"),
                "item_max": _as_optional_float(row["item_max"], "item_max"),
                "is_total": _as_bool(row["is_total"], "is_total"),
            }
            items.append(ItemDefinition(**values))
        return cls(items)

    @classmethod
    def from_csv(cls, path):
        return cls.from_dataframe(pd.read_csv(path))

    @classmethod
    def from_json(cls, path_or_payload):
        if isinstance(path_or_payload, Path):
            payload = json.loads(path_or_payload.read_text(encoding="utf-8"))
        elif isinstance(path_or_payload, str):
            try:
                payload = json.loads(path_or_payload)
            except json.JSONDecodeError:
                payload = json.loads(Path(path_or_payload).read_text(encoding="utf-8"))
        else:
            payload = path_or_payload
        rows = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ContractError("Scale map JSON must contain an 'items' list.")
        return cls.from_dataframe(pd.DataFrame(rows))

    def _validate(self):
        if not self.items:
            raise ContractError("Scale map must contain at least one item.")
        for item in self.items:
            if not item.scale or not item.dimension_code or not item.column_name:
                raise ContractError("Scale map names and column_name cannot be empty.")
            if item.item_number < 1:
                raise ContractError("Scale map item_number must be positive.")
            if item.item_min is not None and item.item_max is not None:
                if item.item_min >= item.item_max:
                    raise ContractError(
                        f"Invalid response range for '{item.column_name}'."
                    )

        seen = set()
        for item in self.items:
            key = (item.scale, item.dimension_code, item.column_name)
            if key in seen:
                raise ContractError(
                    "Duplicate scale-map item: "
                    f"{item.scale}/{item.dimension_code}/{item.column_name}"
                )
            seen.add(key)

    def to_dataframe(self):
        return pd.DataFrame([
            {
                "scale": item.scale,
                "dimension_code": item.dimension_code,
                "dimension_label": item.dimension_label,
                "item_number": item.item_number,
                "column_name": item.column_name,
                "reverse": item.reverse,
                "item_min": item.item_min,
                "item_max": item.item_max,
                "is_total": item.is_total,
            }
            for item in self.items
        ], columns=REQUIRED_SCALE_MAP_COLUMNS)

    def to_json(self):
        return json.dumps({"items": self.to_dataframe().to_dict("records")}, indent=2)

    def scales(self):
        return tuple(dict.fromkeys(item.scale for item in self.items))

    def dimensions(self, scale=None):
        selected = [item for item in self.items if scale is None or item.scale == scale]
        grouped = {}
        for item in selected:
            key = (item.scale, item.dimension_code, item.dimension_label, item.is_total)
            grouped.setdefault(key, []).append(item)
        return tuple(
            DimensionDefinition(
                scale=key[0],
                code=key[1],
                label=key[2],
                items=tuple(sorted(items, key=lambda item: item.item_number)),
                is_total=key[3],
            )
            for key, items in grouped.items()
        )

    def missing_columns(self, columns, scale=None):
        available = set(columns)
        return sorted({
            item.column_name
            for item in self.items
            if (scale is None or item.scale == scale)
            and item.column_name not in available
        })


@dataclass
class ScoringReport:
    """Summary of a metadata-driven scoring operation."""

    scales: list[str]
    reversed_items: list[str] = field(default_factory=list)
    composites: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "scales": list(self.scales),
            "reversed_items": list(self.reversed_items),
            "composites": list(self.composites),
            "warnings": list(self.warnings),
        }


class ScoringEngine:
    """Apply item keying and composite definitions without mutating input."""

    def score(self, frame, scale_map, scale=None):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Scoring requires a pandas DataFrame.")
        instrument = InstrumentDefinition.from_scale_map(scale_map, scale) if scale else None
        selected_scales = [instrument.name] if instrument else list(scale_map.scales())
        missing = scale_map.missing_columns(frame.columns, scale)
        if missing:
            raise ContractError(
                "Scale map references columns not found in the data: "
                + ", ".join(missing)
            )

        result = frame.copy()
        report = ScoringReport(scales=selected_scales)
        seen_items = {}
        for item in (
            instrument.items if instrument
            else tuple(item for item in scale_map.items if item.scale in selected_scales)
        ):
            scoring_config = (item.reverse, item.item_min, item.item_max)
            previous = seen_items.get(item.column_name)
            if previous and previous != scoring_config:
                raise ContractError(
                    f"Conflicting scoring metadata for '{item.column_name}'."
                )
            if previous:
                continue
            seen_items[item.column_name] = scoring_config

            numeric = pd.to_numeric(result[item.column_name], errors="coerce")
            invalid = int((result[item.column_name].notna() & numeric.isna()).sum())
            if invalid:
                report.warnings.append(
                    f"{item.column_name}: {invalid} non-numeric response(s) became missing."
                )
            if item.reverse:
                if item.item_min is None or item.item_max is None:
                    raise ContractError(
                        f"Reverse-coded item '{item.column_name}' needs item_min and item_max."
                    )
                numeric = (item.item_min + item.item_max) - numeric
                report.reversed_items.append(item.column_name)
            result[item.column_name] = numeric

        dimensions = (
            instrument.dimensions
            if instrument
            else tuple(scale_map.dimensions(name) for name in selected_scales)
        )
        if not instrument:
            dimensions = tuple(dimension for group in dimensions for dimension in group)
        for dimension in dimensions:
            if dimension.code in result.columns and dimension.code not in seen_items:
                raise ContractError(
                    f"Composite column '{dimension.code}' already exists."
                )
            columns = [item.column_name for item in dimension.items]
            values = result[columns]
            result[dimension.code] = values.sum(axis=1, min_count=dimension.min_valid)
            report.composites.append(dimension.code)

        return result, report


@dataclass
class ReliabilityReport:
    """Reliability summary for one dimension."""

    scale: str
    dimension_code: str
    dimension_label: str
    n_items: int
    n_rows: int
    complete_rows: int
    alpha: float | None
    omega: float | None
    flag: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "scale": self.scale,
            "dimension_code": self.dimension_code,
            "dimension_label": self.dimension_label,
            "n_items": self.n_items,
            "n_rows": self.n_rows,
            "complete_rows": self.complete_rows,
            "alpha": self.alpha,
            "omega": self.omega,
            "flag": self.flag,
            "warnings": list(self.warnings),
        }


def _cronbach_alpha(values):
    if values.shape[1] < 2:
        return None
    if len(values) < 2:
        return None
    variances = values.var(axis=0, ddof=1)
    total_variance = values.sum(axis=1).var(ddof=1)
    if pd.isna(total_variance) or total_variance == 0:
        return None
    return float(
        values.shape[1] / (values.shape[1] - 1)
        * (1 - variances.sum() / total_variance)
    )


def reliability_report(frame, scale_map, scale=None, low_alpha=0.60):
    """Return one reliability record per declared dimension.

    Omega is intentionally reported as unavailable until a validated factor
    model implementation is added; it is never substituted with alpha.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ContractError("Reliability requires a pandas DataFrame.")
    missing = scale_map.missing_columns(frame.columns, scale)
    if missing:
        raise ContractError(
            "Scale map references columns not found in the data: "
            + ", ".join(missing)
        )

    reports = []
    for dimension in scale_map.dimensions(scale):
        columns = [item.column_name for item in dimension.items]
        values = frame[columns].apply(pd.to_numeric, errors="coerce")
        complete = values.dropna()
        warnings = ["omega is not implemented; alpha is reported only."]
        alpha = _cronbach_alpha(complete)
        flag = ""
        if alpha is None:
            warnings.append("alpha could not be estimated from complete rows.")
        elif alpha < low_alpha:
            flag = f"LOW (<{low_alpha:.2f})"
        reports.append(ReliabilityReport(
            scale=dimension.scale,
            dimension_code=dimension.code,
            dimension_label=dimension.label,
            n_items=len(columns),
            n_rows=len(values),
            complete_rows=len(complete),
            alpha=alpha,
            omega=None,
            flag=flag,
            warnings=warnings,
        ))
    return reports
