"""Typed analysis specifications, APIM estimation, and result serialization."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

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
            "estimator": self.estimator,
            "missing_data": self.missing_data,
            "exploratory": self.exploratory,
        }


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
        self.adapters = dict(adapters or {"apim_ols": _run_apim_ols})

    def run(self, frame, spec):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Analysis input must be a pandas DataFrame.")
        if not isinstance(spec, AnalysisSpec):
            raise ContractError("AnalysisRunner requires an AnalysisSpec.")
        adapter = self.adapters.get(spec.estimator)
        if adapter is None:
            raise ContractError(f"Unknown analysis estimator '{spec.estimator}'.")
        return adapter(frame, spec)


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
