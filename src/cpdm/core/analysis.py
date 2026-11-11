"""Typed analysis specifications, APIM estimation, and result serialization."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from numpy.random import default_rng

import numpy as np
import pandas as pd

from cpdm.core.contracts import ContractError


ANALYSIS_VERSION = 1
MISSING_POLICIES = {"complete_case", "pairwise"}


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _fingerprint(frame):
    payload = pd.util.hash_pandas_object(frame, index=True).values.tobytes()
    columns = json.dumps([str(column) for column in frame.columns]).encode("utf-8")
    return hashlib.sha256(columns + payload).hexdigest()


@dataclass(frozen=True)
class AnalysisSpec:
    """A serializable description of one analysis request."""

    name: str
    predictors: tuple[str, ...] = ()
    mediators: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    moderators: tuple[str, ...] = ()
    covariates: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    subject: str | None = None
    time: str | None = None
    cluster: str | None = None
    weights: str | None = None
    seed: int = 0
    estimator: str = "apim_ols"
    missing_data: str = "complete_case"
    exploratory: bool = False

    def __post_init__(self):
        if not str(self.name).strip():
            raise ContractError("Analysis name cannot be empty.")
        if self.missing_data not in MISSING_POLICIES:
            raise ContractError(
                f"Unsupported missing-data policy '{self.missing_data}'."
            )
        if not self.predictors or not self.outcomes:
            raise ContractError("AnalysisSpec needs at least one predictor and outcome.")
        object.__setattr__(self, "predictors", _as_tuple(self.predictors))
        object.__setattr__(self, "mediators", _as_tuple(self.mediators))
        object.__setattr__(self, "outcomes", _as_tuple(self.outcomes))
        object.__setattr__(self, "moderators", _as_tuple(self.moderators))
        object.__setattr__(self, "covariates", _as_tuple(self.covariates))
        object.__setattr__(self, "roles", _as_tuple(self.roles))

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            raise ContractError("Analysis specification must be a JSON object.")
        values = dict(payload)
        values.pop("version", None)
        return cls(**values)

    def as_dict(self):
        return {
            "version": ANALYSIS_VERSION,
            "name": self.name,
            "predictors": list(self.predictors),
            "mediators": list(self.mediators),
            "outcomes": list(self.outcomes),
            "moderators": list(self.moderators),
            "covariates": list(self.covariates),
            "roles": list(self.roles),
            "subject": self.subject,
            "time": self.time,
            "cluster": self.cluster,
            "weights": self.weights,
            "seed": self.seed,
            "estimator": self.estimator,
            "missing_data": self.missing_data,
            "exploratory": self.exploratory,
        }


@dataclass(frozen=True)
class AnalysisCapability:
    """Metadata describing an analysis adapter's contract."""

    name: str
    description: str
    required_roles: tuple[str, ...] = ()
    supported_missing_data: tuple[str, ...] = tuple(sorted(MISSING_POLICIES))

    def __post_init__(self):
        if not str(self.name).strip():
            raise ContractError("Analysis capability name cannot be empty.")
        object.__setattr__(self, "required_roles", _as_tuple(self.required_roles))
        object.__setattr__(
            self, "supported_missing_data", _as_tuple(self.supported_missing_data)
        )

    def validate(self, spec):
        if spec.estimator != self.name:
            raise ContractError(
                f"Capability '{self.name}' cannot run estimator '{spec.estimator}'."
            )
        if spec.missing_data not in self.supported_missing_data:
            raise ContractError(
                f"Estimator '{self.name}' does not support missing-data policy "
                f"'{spec.missing_data}'."
            )
        missing = [
            role for role in self.required_roles
            if not getattr(spec, role, ())
        ]
        if missing:
            raise ContractError(
                f"Estimator '{self.name}' requires: {', '.join(missing)}."
            )

    def as_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "required_roles": list(self.required_roles),
            "supported_missing_data": list(self.supported_missing_data),
        }


@dataclass(frozen=True)
class AnalysisAdapter:
    """A callable analysis implementation paired with its capability metadata."""

    capability: AnalysisCapability
    run: object


class AnalysisRegistry:
    """Register and discover method-agnostic analysis adapters."""

    def __init__(self):
        self._adapters = {}

    def register(self, adapter):
        if not isinstance(adapter, AnalysisAdapter):
            raise ContractError("Analysis adapter must be an AnalysisAdapter.")
        name = adapter.capability.name
        if name in self._adapters:
            raise ContractError(f"Analysis estimator '{name}' is already registered.")
        self._adapters[name] = adapter

    def get(self, name):
        try:
            return self._adapters[name]
        except KeyError:
            raise ContractError(f"Unknown analysis estimator '{name}'.") from None

    def capabilities(self):
        return tuple(
            adapter.capability for adapter in self._adapters.values()
        )


@dataclass(frozen=True)
class EffectEstimate:
    """One named model effect and its diagnostics."""

    path: str
    estimate: float
    standard_error: float | None = None
    confidence_interval: tuple[float, float] | None = None
    p_value: float | None = None
    role: str | None = None
    diagnostics: dict = field(default_factory=dict)

    def as_dict(self):
        interval = None
        if self.confidence_interval is not None:
            interval = list(self.confidence_interval)
        return {
            "path": self.path,
            "estimate": self.estimate,
            "standard_error": self.standard_error,
            "confidence_interval": interval,
            "p_value": self.p_value,
            "role": self.role,
            "diagnostics": dict(self.diagnostics),
        }


@dataclass
class AnalysisResult:
    """Stable output from an analysis runner."""

    spec: AnalysisSpec
    estimates: list[EffectEstimate]
    input_fingerprint: str
    warnings: list[str] = field(default_factory=list)
    convergence_status: str = "converged"
    metadata: dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self):
        return {
            "kind": "cpdm-analysis-result",
            "version": ANALYSIS_VERSION,
            "spec": self.spec.as_dict(),
            "input_fingerprint": self.input_fingerprint,
            "warnings": list(self.warnings),
            "convergence_status": self.convergence_status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "estimates": [estimate.as_dict() for estimate in self.estimates],
        }


class AnalysisRunner:
    """Validate an input frame and dispatch to a small analysis adapter."""

    def __init__(self, adapters=None):
        self.registry = AnalysisRegistry()
        if adapters is None:
            adapters = {
                "apim_ols": _run_apim_ols,
                "linear_regression": _run_linear_regression,
                "weighted_regression": _run_weighted_regression,
                "clustered_regression": _run_clustered_regression,
                "longitudinal_regression": _run_longitudinal_regression,
                "repeated_measures_regression": _run_repeated_measures_regression,
                "bootstrap_indirect": _run_bootstrap_indirect,
            }
        for name, function in adapters.items():
            required = {
                "weighted_regression": ("predictors", "outcomes", "weights"),
                "clustered_regression": ("predictors", "outcomes", "cluster"),
                "longitudinal_regression": ("predictors", "outcomes", "subject", "time"),
                "repeated_measures_regression": (
                    "predictors", "outcomes", "subject", "time"
                ),
                "bootstrap_indirect": ("predictors", "mediators", "outcomes"),
            }.get(name, ("predictors", "outcomes"))
            supported_missing_data = (
                ("complete_case",)
                if name == "bootstrap_indirect"
                else tuple(sorted(MISSING_POLICIES))
            )
            self.registry.register(
                AnalysisAdapter(
                    AnalysisCapability(
                        name=name,
                        description=f"{name} analysis adapter",
                        required_roles=required,
                        supported_missing_data=supported_missing_data,
                    ),
                    function,
                )
            )

    def run(self, frame, spec):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Analysis input must be a pandas DataFrame.")
        if not isinstance(spec, AnalysisSpec):
            raise ContractError("AnalysisRunner requires an AnalysisSpec.")
        adapter = self.registry.get(spec.estimator)
        adapter.capability.validate(spec)
        return adapter.run(frame, spec)

    def capability_metadata(self):
        return [capability.as_dict() for capability in self.registry.capabilities()]


def descriptive_summary(frame, columns=None, group_by=None):
    """Return stable descriptive summaries for numeric variables."""
    if not isinstance(frame, pd.DataFrame):
        raise ContractError("Descriptive summaries require a pandas DataFrame.")
    columns = list(columns or frame.select_dtypes(include="number").columns)
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ContractError("Unknown summary column(s): " + ", ".join(missing))
    grouped = frame.groupby(group_by, dropna=False) if group_by else [(None, frame)]
    rows = []
    for group, subset in grouped:
        for column in columns:
            values = pd.to_numeric(subset[column], errors="coerce").dropna()
            rows.append({
                "group": group,
                "variable": column,
                "n": int(values.size),
                "mean": float(values.mean()) if len(values) else None,
                "std": float(values.std(ddof=1)) if len(values) > 1 else None,
                "min": float(values.min()) if len(values) else None,
                "max": float(values.max()) if len(values) else None,
            })
    return pd.DataFrame(rows)


def compare_groups(frame, value, group):
    """Compare two groups with transparent descriptive effect statistics."""
    if value not in frame or group not in frame:
        raise ContractError("Group comparisons require value and group columns.")
    levels = list(frame[group].dropna().unique())
    if len(levels) != 2:
        raise ContractError("Group comparisons require exactly two groups.")
    samples = [
        pd.to_numeric(frame.loc[frame[group] == level, value], errors="coerce").dropna()
        for level in levels
    ]
    means = [float(sample.mean()) if len(sample) else None for sample in samples]
    return {
        "value": value,
        "group": group,
        "levels": [str(level) for level in levels],
        "n": [int(len(sample)) for sample in samples],
        "means": means,
        "mean_difference": means[0] - means[1] if all(item is not None for item in means) else None,
    }


def repeated_measures_summary(frame, subject, time, value):
    """Summarize a repeated-measures variable by time point."""
    required = {subject, time, value}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError("Repeated-measures columns missing: " + ", ".join(missing))
    result = (
        frame.assign(_value=pd.to_numeric(frame[value], errors="coerce"))
        .groupby(time, dropna=False)
        .agg(n=("_value", "count"), mean=("_value", "mean"), std=("_value", "std"))
        .reset_index()
    )
    return result


def _run_linear_regression(frame, spec):
    columns = [*spec.predictors, *spec.outcomes]
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ContractError("Analysis columns missing: " + ", ".join(missing))
    estimates = []
    for outcome in spec.outcomes:
        selected = frame[[*spec.predictors, outcome]].apply(pd.to_numeric, errors="coerce")
        selected = selected.dropna()
        if selected.empty:
            raise ContractError(f"No complete observations for outcome '{outcome}'.")
        x = np.column_stack([np.ones(len(selected)), selected[list(spec.predictors)]])
        coefficients, *_ = np.linalg.lstsq(x, selected[outcome].to_numpy(), rcond=None)
        for predictor, coefficient in zip(spec.predictors, coefficients[1:]):
            estimates.append(EffectEstimate(
                path=f"{predictor}->{outcome}",
                estimate=float(coefficient),
                role="regression",
                diagnostics={"n": int(len(selected))},
            ))
    return AnalysisResult(spec, estimates, _fingerprint(frame))


def _validate_columns(frame, columns, label="Analysis"):
    requested = [column for column in columns if column]
    missing = sorted(set(requested) - set(frame.columns))
    if missing:
        raise ContractError(f"{label} columns missing: " + ", ".join(missing))


def _run_weighted_regression(frame, spec):
    if not spec.weights:
        raise ContractError("Weighted regression requires a weights column.")
    _validate_columns(
        frame, [*spec.predictors, *spec.outcomes, spec.weights], "Weighted regression"
    )
    estimates = []
    for outcome in spec.outcomes:
        selected = frame[[*spec.predictors, outcome, spec.weights]].apply(
            pd.to_numeric, errors="coerce"
        ).dropna()
        if (selected[spec.weights] <= 0).any():
            raise ContractError("Regression weights must be positive.")
        x = np.column_stack([np.ones(len(selected)), selected[list(spec.predictors)]])
        weight = np.sqrt(selected[spec.weights].to_numpy())
        coefficients, *_ = np.linalg.lstsq(
            x * weight[:, None], selected[outcome].to_numpy() * weight, rcond=None
        )
        for predictor, coefficient in zip(spec.predictors, coefficients[1:]):
            estimates.append(EffectEstimate(
                path=f"{predictor}->{outcome}",
                estimate=float(coefficient),
                role="weighted_regression",
                diagnostics={"n": int(len(selected)), "weights": spec.weights},
            ))
    return AnalysisResult(spec, estimates, _fingerprint(frame))


def _run_clustered_regression(frame, spec):
    if not spec.cluster:
        raise ContractError("Clustered regression requires a cluster column.")
    _validate_columns(
        frame, [*spec.predictors, *spec.outcomes, spec.cluster], "Clustered regression"
    )
    result = _run_linear_regression(frame, spec)
    clusters = frame[spec.cluster].dropna().nunique()
    if clusters < 2:
        raise ContractError("Clustered regression requires at least two clusters.")
    result.estimates = [
        EffectEstimate(
            path=estimate.path,
            estimate=estimate.estimate,
            standard_error=estimate.standard_error,
            confidence_interval=estimate.confidence_interval,
            p_value=estimate.p_value,
            role="clustered_regression",
            diagnostics={
                **estimate.diagnostics,
                "cluster": spec.cluster,
                "cluster_count": int(clusters),
            },
        )
        for estimate in result.estimates
    ]
    return result


def _run_longitudinal_regression(frame, spec):
    if not spec.subject or not spec.time:
        raise ContractError("Longitudinal regression requires subject and time columns.")
    _validate_columns(
        frame, [*spec.predictors, *spec.outcomes, spec.subject, spec.time],
        "Longitudinal regression",
    )
    if frame.duplicated([spec.subject, spec.time]).any():
        raise ContractError("Longitudinal observations must be unique by subject and time.")
    result = _run_linear_regression(frame, spec)
    result.estimates = [
        EffectEstimate(
            path=estimate.path,
            estimate=estimate.estimate,
            standard_error=estimate.standard_error,
            confidence_interval=estimate.confidence_interval,
            p_value=estimate.p_value,
            role="longitudinal_regression",
            diagnostics={
                **estimate.diagnostics,
                "subject": spec.subject,
                "time": spec.time,
            },
        )
        for estimate in result.estimates
    ]
    return result


def _run_repeated_measures_regression(frame, spec):
    result = _run_longitudinal_regression(frame, spec)
    result.estimates = [
        EffectEstimate(
            path=estimate.path,
            estimate=estimate.estimate,
            standard_error=estimate.standard_error,
            confidence_interval=estimate.confidence_interval,
            p_value=estimate.p_value,
            role="repeated_measures_regression",
            diagnostics={**estimate.diagnostics, "repeated_measures": True},
        )
        for estimate in result.estimates
    ]
    return result


def _run_bootstrap_indirect(frame, spec):
    if len(spec.predictors) != 1 or len(spec.mediators) != 1 or len(spec.outcomes) != 1:
        raise ContractError("Indirect effects require one predictor, mediator, and outcome.")
    predictor, mediator, outcome = spec.predictors[0], spec.mediators[0], spec.outcomes[0]
    _validate_columns(frame, [predictor, mediator, outcome], "Indirect-effect")
    selected = frame[[predictor, mediator, outcome]].apply(
        pd.to_numeric, errors="coerce"
    ).dropna()
    if len(selected) < 3:
        raise ContractError("Indirect effects require at least three complete rows.")
    rng = default_rng(spec.seed)
    effects = []
    for _ in range(500):
        sample = selected.iloc[rng.integers(0, len(selected), len(selected))]
        try:
            a = _slope(sample[predictor].to_numpy(), sample[mediator].to_numpy())
            b = _slope(sample[mediator].to_numpy(), sample[outcome].to_numpy())
        except ContractError:
            continue
        effects.append(a * b)
    if len(effects) < 100:
        raise ContractError("Too many degenerate bootstrap samples for an interval.")
    observed_a = _slope(selected[predictor], selected[mediator])
    observed_b = _slope(selected[mediator], selected[outcome])
    ci = (float(np.quantile(effects, 0.025)), float(np.quantile(effects, 0.975)))
    warnings = []
    if len(effects) < 500:
        warnings.append(
            f"{500 - len(effects)} degenerate bootstrap samples were omitted."
        )
    return AnalysisResult(
        spec,
        [EffectEstimate(
            path=f"{predictor}->{mediator}->{outcome}",
            estimate=float(observed_a * observed_b),
            confidence_interval=ci,
            role="indirect_effect",
            diagnostics={"bootstrap_replicates": 500, "seed": spec.seed},
        )],
        _fingerprint(frame),
        warnings=warnings,
    )


def _slope(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    centered = x - x.mean()
    denominator = np.dot(centered, centered)
    if denominator == 0:
        raise ContractError("Cannot estimate a slope from a constant variable.")
    return float(np.dot(centered, y - y.mean()) / denominator)


class ReportWriter:
    """Write analysis results with stable machine-readable columns."""

    COLUMNS = (
        "analysis",
        "path",
        "role",
        "estimate",
        "standard_error",
        "ci_low",
        "ci_high",
        "p_value",
        "convergence_status",
    )

    @classmethod
    def table(cls, result):
        rows = []
        for estimate in result.estimates:
            low, high = (None, None)
            if estimate.confidence_interval is not None:
                low, high = estimate.confidence_interval
            rows.append({
                "analysis": result.spec.name,
                "path": estimate.path,
                "role": estimate.role,
                "estimate": estimate.estimate,
                "standard_error": estimate.standard_error,
                "ci_low": low,
                "ci_high": high,
                "p_value": estimate.p_value,
                "convergence_status": result.convergence_status,
            })
        return pd.DataFrame(rows, columns=cls.COLUMNS)

    @classmethod
    def write_json(cls, result, path):
        Path(path).write_text(
            json.dumps(result.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def write_csv(cls, result, path):
        cls.table(result).to_csv(path, index=False)

    @classmethod
    def write_xlsx(cls, result, path):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            cls.table(result).to_excel(writer, sheet_name="estimates", index=False)
            pd.DataFrame(
                [{"warning": warning} for warning in result.warnings]
            ).to_excel(writer, sheet_name="warnings", index=False)


def _normal_p_value(statistic):
    return math.erfc(abs(statistic) / math.sqrt(2))


def _fit_ols(frame, outcome, predictors):
    values = frame[[outcome, *predictors]].apply(pd.to_numeric, errors="coerce")
    values = values.dropna()
    if len(values) <= len(predictors) + 1:
        raise ContractError(
            f"Insufficient complete rows for outcome '{outcome}'."
        )
    x = np.column_stack([np.ones(len(values)), values[list(predictors)].to_numpy()])
    y = values[outcome].to_numpy()
    coefficients, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ coefficients
    degrees = len(y) - x.shape[1]
    if degrees <= 0 or rank < x.shape[1]:
        raise ContractError(f"Singular design for outcome '{outcome}'.")
    variance = float((residuals @ residuals) / degrees)
    covariance = variance * np.linalg.inv(x.T @ x)
    errors = np.sqrt(np.maximum(np.diag(covariance), 0))
    return coefficients[1:], errors[1:], len(values)


def _run_apim_ols(frame, spec):
    roles = spec.roles or ("h", "w")
    if len(roles) != 2:
        raise ContractError("The APIM adapter requires exactly two roles.")
    if len(spec.predictors) != 1 or len(spec.outcomes) != 1:
        raise ContractError("The APIM adapter currently supports one predictor and outcome.")
    predictor, outcome = spec.predictors[0], spec.outcomes[0]
    warnings = []
    estimates = []
    required = [f"{predictor}_{role}" for role in roles]
    required += [f"{outcome}_{role}" for role in roles]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ContractError("APIM input is missing column(s): " + ", ".join(missing))

    for role, partner in zip(roles, roles[::-1]):
        predictors = (f"{predictor}_{role}", f"{predictor}_{partner}")
        try:
            coefficients, errors, observations = _fit_ols(
                frame, f"{outcome}_{role}", predictors
            )
        except ContractError as exc:
            warnings.append(str(exc))
            continue
        for label, estimate, error in zip(("actor", "partner"), coefficients, errors):
            statistic = estimate / error if error else 0.0
            estimates.append(
                EffectEstimate(
                    path=f"{label}:{predictor}->{outcome}",
                    estimate=float(estimate),
                    standard_error=float(error),
                    confidence_interval=(
                        float(estimate - 1.96 * error),
                        float(estimate + 1.96 * error),
                    ),
                    p_value=float(_normal_p_value(statistic)),
                    role=role,
                    diagnostics={"observations": observations, "partner_role": partner},
                )
            )
    status = "converged" if len(estimates) == 4 else "incomplete"
    return AnalysisResult(
        spec=spec,
        estimates=estimates,
        input_fingerprint=_fingerprint(frame),
        warnings=warnings,
        convergence_status=status,
        metadata={"adapter": "apim_ols", "roles": list(roles)},
    )
