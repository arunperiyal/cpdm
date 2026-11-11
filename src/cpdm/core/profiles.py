"""Metadata contracts for latent profiles and other mixture analyses."""

from dataclasses import dataclass
import math
import json
from pathlib import Path
import re

import pandas as pd

from cpdm.core.contracts import ContractError


MEASUREMENT_LEVELS = {"continuous", "ordinal", "categorical"}
MISSING_POLICIES = {"error", "drop", "impute"}
TRANSFORMS = {"identity", "log", "sqrt", "zscore"}


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _safe_name(value, field):
    value = str(value).strip()
    if not value:
        raise ContractError(f"{field} cannot be empty.")
    if not re.match(r"^[A-Za-z][A-Za-z0-9_.-]*$", value):
        raise ContractError(
            f"{field} must start with a letter and contain only letters, "
            "numbers, '.', '-', or '_'."
        )
    return value


@dataclass(frozen=True)
class IndicatorDefinition:
    """One observed variable and its preparation metadata."""

    name: str
    source_column: str
    measurement_level: str = "continuous"
    allowed_values: tuple[str, ...] = ()
    transform: str = "identity"
    standardize: bool = False
    missing_policy: str = "drop"
    role: str = "indicator"

    def __post_init__(self):
        object.__setattr__(self, "name", _safe_name(self.name, "Indicator name"))
        source = str(self.source_column).strip()
        if not source:
            raise ContractError("Indicator source_column cannot be empty.")
        object.__setattr__(self, "source_column", source)
        if self.measurement_level not in MEASUREMENT_LEVELS:
            raise ContractError(
                f"Unsupported measurement level '{self.measurement_level}'."
            )
        if self.transform not in TRANSFORMS:
            raise ContractError(f"Unsupported indicator transform '{self.transform}'.")
        if self.missing_policy not in MISSING_POLICIES:
            raise ContractError(
                f"Unsupported indicator missing policy '{self.missing_policy}'."
            )
        if self.role not in {"indicator", "identifier", "weight", "group", "time"}:
            raise ContractError(f"Unsupported indicator role '{self.role}'.")
        object.__setattr__(self, "allowed_values", _as_tuple(self.allowed_values))
        if self.role != "indicator":
            raise ContractError(
                "Profile indicators must have role 'indicator'; keep identifiers, "
                "weights, groups, and time fields outside the indicator list."
            )

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            raise ContractError("Indicator definition must be a JSON object.")
        values = dict(payload)
        values.pop("version", None)
        return cls(**values)

    def as_dict(self):
        return {
            "name": self.name,
            "source_column": self.source_column,
            "measurement_level": self.measurement_level,
            "allowed_values": list(self.allowed_values),
            "transform": self.transform,
            "standardize": self.standardize,
            "missing_policy": self.missing_policy,
            "role": self.role,
        }

    def validate_frame(self, frame):
        if self.source_column not in frame.columns:
            raise ContractError(
                f"Profile indicator is missing source column '{self.source_column}'."
            )
        if self.allowed_values:
            observed = set(frame[self.source_column].dropna().astype(str))
            invalid = sorted(observed - set(self.allowed_values))
            if invalid:
                raise ContractError(
                    f"Indicator '{self.name}' contains values outside its allowed "
                    f"set: {', '.join(invalid)}."
                )
        if self.measurement_level == "continuous":
            numeric = pd.to_numeric(frame[self.source_column], errors="coerce")
            invalid = frame[self.source_column].notna() & numeric.isna()
            if invalid.any():
                raise ContractError(
                    f"Continuous indicator '{self.name}' contains non-numeric values."
                )
        return self

    def prepare(self, series):
        """Apply declared missing-value and numeric transformations."""
        values = series.copy()
        if self.missing_policy == "error" and values.isna().any():
            raise ContractError(f"Indicator '{self.name}' contains missing values.")
        if self.measurement_level in {"continuous", "ordinal"}:
            values = pd.to_numeric(values, errors="coerce")
            if self.missing_policy == "error" and values.isna().any():
                raise ContractError(f"Indicator '{self.name}' contains non-numeric values.")
            if self.missing_policy == "impute":
                if values.dropna().empty:
                    raise ContractError(f"Indicator '{self.name}' has no values to impute.")
                values = values.fillna(values.median())
            if self.transform == "log":
                if (values.dropna() < 0).any():
                    raise ContractError(f"Indicator '{self.name}' cannot apply log to negatives.")
                values = values.map(lambda value: None if pd.isna(value) else math.log1p(value))
            elif self.transform == "sqrt":
                if (values.dropna() < 0).any():
                    raise ContractError(f"Indicator '{self.name}' cannot apply sqrt to negatives.")
                values = values.map(lambda value: None if pd.isna(value) else math.sqrt(value))
            if self.standardize or self.transform == "zscore":
                mean = values.mean()
                std = values.std(ddof=0)
                if pd.isna(std) or std == 0:
                    raise ContractError(f"Indicator '{self.name}' cannot be standardized.")
                values = (values - mean) / std
        elif self.missing_policy == "impute" and values.isna().any():
            if values.dropna().empty:
                raise ContractError(f"Indicator '{self.name}' has no values to impute.")
            values = values.fillna(values.mode().iloc[0])
        return values


@dataclass(frozen=True)
class ProfileAnalysisSpec:
    """Serializable, backend-neutral specification for a profile analysis."""

    name: str
    indicators: tuple[IndicatorDefinition, ...]
    class_counts: tuple[int, ...] = (2, 3, 4)
    estimator: str = "gaussian_mixture"
    covariance_structure: str = "full"
    starts: int = 20
    weights: str | None = None
    covariates: tuple[str, ...] = ()
    identifier_columns: tuple[str, ...] = ()
    seed: int = 0
    exploratory: bool = True

    def __post_init__(self):
        object.__setattr__(self, "name", _safe_name(self.name, "Profile analysis name"))
        indicators = tuple(self.indicators)
        if not indicators:
            raise ContractError("ProfileAnalysisSpec needs at least one indicator.")
        if any(not isinstance(item, IndicatorDefinition) for item in indicators):
            raise ContractError("All profile indicators must be IndicatorDefinition objects.")
        names = [item.name for item in indicators]
        if len(names) != len(set(names)):
            raise ContractError("Profile indicator names must be unique.")
        sources = [item.source_column for item in indicators]
        if len(sources) != len(set(sources)):
            raise ContractError("Profile indicator source columns must be unique.")
        class_counts = tuple(int(value) for value in self.class_counts)
        if not class_counts or any(value < 2 for value in class_counts):
            raise ContractError("Profile class_counts must contain values of at least 2.")
        if len(set(class_counts)) != len(class_counts):
            raise ContractError("Profile class_counts must be unique.")
        if self.starts < 1:
            raise ContractError("Profile starts must be positive.")
        if not str(self.estimator).strip():
            raise ContractError("Profile estimator cannot be empty.")
        if not str(self.covariance_structure).strip():
            raise ContractError("Profile covariance_structure cannot be empty.")
        object.__setattr__(self, "indicators", indicators)
        object.__setattr__(self, "class_counts", class_counts)
        object.__setattr__(self, "covariates", _as_tuple(self.covariates))
        object.__setattr__(self, "identifier_columns", _as_tuple(self.identifier_columns))

        indicator_sources = set(sources)
        leakage = indicator_sources & (
            set(self.identifier_columns) | set(self.covariates)
        )
        if self.weights:
            leakage.add(self.weights) if self.weights in indicator_sources else None
        if leakage:
            raise ContractError(
                "Identifiers, covariates, and weights cannot also be indicators: "
                + ", ".join(sorted(leakage))
            )

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            raise ContractError("Profile analysis specification must be a JSON object.")
        values = dict(payload)
        values.pop("version", None)
        values["indicators"] = tuple(
            IndicatorDefinition.from_dict(item) for item in values.get("indicators", ())
        )
        return cls(**values)

    def as_dict(self):
        return {
            "version": 1,
            "name": self.name,
            "indicators": [item.as_dict() for item in self.indicators],
            "class_counts": list(self.class_counts),
            "estimator": self.estimator,
            "covariance_structure": self.covariance_structure,
            "starts": self.starts,
            "weights": self.weights,
            "covariates": list(self.covariates),
            "identifier_columns": list(self.identifier_columns),
            "seed": self.seed,
            "exploratory": self.exploratory,
        }

    def validate_frame(self, frame):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Profile analysis input must be a pandas DataFrame.")
        missing_ids = sorted(set(self.identifier_columns) - set(frame.columns))
        if missing_ids:
            raise ContractError(
                "Profile input is missing identifier column(s): " + ", ".join(missing_ids)
            )
        missing_covariates = sorted(set(self.covariates) - set(frame.columns))
        if missing_covariates:
            raise ContractError(
                "Profile input is missing covariate column(s): "
                + ", ".join(missing_covariates)
            )
        if self.weights and self.weights not in frame.columns:
            raise ContractError(f"Profile input is missing weight column '{self.weights}'.")
        for indicator in self.indicators:
            indicator.validate_frame(frame)
        return self

    def prepare_indicators(self, frame):
        """Return only prepared indicator columns, preserving declared names."""
        self.validate_frame(frame)
        prepared = {
            indicator.name: indicator.prepare(frame[indicator.source_column])
            for indicator in self.indicators
        }
        return pd.DataFrame(prepared, index=frame.index)


@dataclass(frozen=True)
class ProfileSolution:
    """A fitted solution independent of the backend that produced it."""

    class_count: int
    class_labels: tuple[str, ...]
    parameters: dict
    assignments: tuple[str, ...]
    posterior_probabilities: tuple[tuple[float, ...], ...]
    class_sizes: dict[str, int]
    profile_labels: dict[str, str] = None

    def __post_init__(self):
        if self.class_count < 2:
            raise ContractError("ProfileSolution class_count must be at least 2.")
        labels = tuple(str(label) for label in self.class_labels)
        if len(labels) != self.class_count or len(set(labels)) != len(labels):
            raise ContractError("Profile solution class labels must be unique and complete.")
        assignments = tuple(str(value) for value in self.assignments)
        probabilities = tuple(
            tuple(float(value) for value in row)
            for row in self.posterior_probabilities
        )
        if len(assignments) != len(probabilities):
            raise ContractError(
                "Profile assignments and posterior rows must have equal lengths."
            )
        for row in probabilities:
            if len(row) != self.class_count or any(value < 0 for value in row):
                raise ContractError("Posterior probabilities have an invalid shape.")
            if not math.isclose(sum(row), 1.0, abs_tol=1e-6):
                raise ContractError("Each posterior probability row must sum to 1.")
        if set(assignments) - set(labels):
            raise ContractError("Profile assignments contain unknown class labels.")
        sizes = {str(key): int(value) for key, value in self.class_sizes.items()}
        if set(sizes) != set(labels) or sum(sizes.values()) != len(assignments):
            raise ContractError("Profile class_sizes must match assignments.")
        profile_labels = dict(self.profile_labels or {})
        unknown_profile_labels = set(profile_labels) - set(labels)
        if unknown_profile_labels:
            raise ContractError("Profile labels contain unknown classes.")
        object.__setattr__(self, "class_labels", labels)
        object.__setattr__(self, "assignments", assignments)
        object.__setattr__(self, "posterior_probabilities", probabilities)
        object.__setattr__(self, "class_sizes", sizes)
        object.__setattr__(self, "profile_labels", profile_labels)

    def as_dict(self):
        return {
            "class_count": self.class_count,
            "class_labels": list(self.class_labels),
            "parameters": self.parameters,
            "assignments": list(self.assignments),
            "posterior_probabilities": [list(row) for row in self.posterior_probabilities],
            "class_sizes": dict(self.class_sizes),
            "profile_labels": dict(self.profile_labels),
        }


@dataclass(frozen=True)
class FitStatistic:
    """Comparable fit and admissibility information for one solution."""

    class_count: int
    log_likelihood: float
    parameter_count: int
    aic: float
    bic: float
    adjusted_bic: float | None = None
    entropy: float | None = None
    likelihood_ratio_p: float | None = None
    warnings: tuple[str, ...] = ()
    admissible: bool = True

    def __post_init__(self):
        if self.class_count < 2 or self.parameter_count < 1:
            raise ContractError("FitStatistic counts must be positive and valid.")
        for name in ("log_likelihood", "aic", "bic"):
            if not math.isfinite(float(getattr(self, name))):
                raise ContractError(f"FitStatistic {name} must be finite.")
        if self.entropy is not None and not 0 <= self.entropy <= 1:
            raise ContractError("FitStatistic entropy must be between 0 and 1.")
        if self.likelihood_ratio_p is not None and not 0 <= self.likelihood_ratio_p <= 1:
            raise ContractError("Likelihood-ratio p-value must be between 0 and 1.")
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))

    def as_dict(self):
        return {
            "class_count": self.class_count,
            "log_likelihood": self.log_likelihood,
            "parameter_count": self.parameter_count,
            "aic": self.aic,
            "bic": self.bic,
            "adjusted_bic": self.adjusted_bic,
            "entropy": self.entropy,
            "likelihood_ratio_p": self.likelihood_ratio_p,
            "warnings": list(self.warnings),
            "admissible": self.admissible,
        }


@dataclass(frozen=True)
class ClassSelectionReport:
    """Evidence and review record for choosing among profile solutions."""

    analysis_name: str
    fit_statistics: tuple[FitStatistic, ...]
    selected_class_count: int | None = None
    decision: str = ""
    review_notes: str = ""
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        if not str(self.analysis_name).strip():
            raise ContractError("ClassSelectionReport analysis_name cannot be empty.")
        statistics = tuple(self.fit_statistics)
        if not statistics:
            raise ContractError("ClassSelectionReport needs fit statistics.")
        counts = [item.class_count for item in statistics]
        if len(counts) != len(set(counts)):
            raise ContractError("Class-selection class counts must be unique.")
        if self.selected_class_count is not None and self.selected_class_count not in counts:
            raise ContractError("Selected class count is not in the fit-statistic report.")
        object.__setattr__(self, "fit_statistics", statistics)
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))

    def as_dict(self):
        return {
            "analysis_name": self.analysis_name,
            "fit_statistics": [item.as_dict() for item in self.fit_statistics],
            "selected_class_count": self.selected_class_count,
            "decision": self.decision,
            "review_notes": self.review_notes,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ProfileStabilityReport:
    """Repeated-start and resampling evidence for one profile solution."""

    class_count: int
    repeated_start_count: int
    agreement_rate: float
    resample_count: int = 0
    resample_agreement_rate: float | None = None
    label_alignment: dict = None
    sensitivity: dict = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        if self.class_count < 2:
            raise ContractError("Profile stability class_count must be at least 2.")
        if self.repeated_start_count < 1:
            raise ContractError("Profile stability needs at least one repeated start.")
        if not 0 <= self.agreement_rate <= 1:
            raise ContractError("Profile stability agreement_rate must be between 0 and 1.")
        if self.resample_count < 0:
            raise ContractError("Profile stability resample_count cannot be negative.")
        if self.resample_agreement_rate is not None and not 0 <= self.resample_agreement_rate <= 1:
            raise ContractError(
                "Profile resample_agreement_rate must be between 0 and 1."
            )
        alignment = dict(self.label_alignment or {})
        sensitivity = dict(self.sensitivity or {})
        object.__setattr__(self, "label_alignment", alignment)
        object.__setattr__(self, "sensitivity", sensitivity)
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))

    def as_dict(self):
        return {
            "class_count": self.class_count,
            "repeated_start_count": self.repeated_start_count,
            "agreement_rate": self.agreement_rate,
            "resample_count": self.resample_count,
            "resample_agreement_rate": self.resample_agreement_rate,
            "label_alignment": dict(self.label_alignment),
            "sensitivity": dict(self.sensitivity),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ProfileAnalysisResult:
    """Portable output from a profile-analysis adapter."""

    spec: ProfileAnalysisSpec
    solution: ProfileSolution
    fit_statistic: FitStatistic
    stability: ProfileStabilityReport | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict = None

    def __post_init__(self):
        if self.solution.class_count != self.fit_statistic.class_count:
            raise ContractError("Solution and fit statistic class counts must match.")
        if self.stability and self.stability.class_count != self.solution.class_count:
            raise ContractError("Stability and solution class counts must match.")
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def as_dict(self):
        return {
            "kind": "cpdm-profile-analysis-result",
            "version": 1,
            "spec": self.spec.as_dict(),
            "solution": self.solution.as_dict(),
            "fit_statistic": self.fit_statistic.as_dict(),
            "stability": self.stability.as_dict() if self.stability else None,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


class MixtureAnalysisRunner:
    """Validate profile inputs and dispatch to a registered backend adapter."""

    def __init__(self, adapters=None):
        self.adapters = dict(adapters or {})

    def register(self, estimator, adapter):
        if not str(estimator).strip() or not callable(adapter):
            raise ContractError("A runner adapter needs a name and callable.")
        self.adapters[str(estimator)] = adapter

    def run(self, frame, spec):
        if not isinstance(spec, ProfileAnalysisSpec):
            raise ContractError("MixtureAnalysisRunner requires a ProfileAnalysisSpec.")
        spec.validate_frame(frame)
        adapter = self.adapters.get(spec.estimator)
        if adapter is None:
            raise ContractError(
                f"No mixture-analysis adapter is registered for '{spec.estimator}'."
            )
        result = adapter(frame, spec)
        if not isinstance(result, ProfileAnalysisResult):
            raise ContractError("Mixture-analysis adapters must return ProfileAnalysisResult.")
        return result


class ProfileResultWriter:
    """Write profile specifications, assignments, and diagnostics."""

    @staticmethod
    def assignments_table(result):
        rows = []
        labels = result.solution.class_labels
        for index, (assignment, posterior) in enumerate(
            zip(result.solution.assignments, result.solution.posterior_probabilities)
        ):
            row = {"observation": index, "assigned_class": assignment}
            row.update({
                f"posterior_{label}": value
                for label, value in zip(labels, posterior)
            })
            rows.append(row)
        return pd.DataFrame(rows)

    @classmethod
    def write_json(cls, result, path):
        Path(path).write_text(
            json.dumps(result.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def write_csv(cls, result, path):
        cls.assignments_table(result).to_csv(path, index=False)

    @classmethod
    def write_xlsx(cls, result, path):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            cls.assignments_table(result).to_excel(
                writer, sheet_name="assignments", index=False
            )
            pd.DataFrame([result.fit_statistic.as_dict()]).to_excel(
                writer, sheet_name="fit", index=False
            )
            pd.DataFrame([{"warning": warning} for warning in result.warnings]).to_excel(
                writer, sheet_name="warnings", index=False
            )
