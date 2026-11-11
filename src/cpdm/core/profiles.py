"""Metadata contracts for latent profiles and other mixture analyses."""

from dataclasses import dataclass
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
