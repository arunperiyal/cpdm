"""Validation for data and portable CPDM definitions.

Validation lives in the core layer so file uploads, the console, and future
batch runners enforce the same contracts before mutating a dataset.
"""

import pandas as pd


class ContractError(ValueError):
    """A user-correctable contract violation."""


def validate_dataframe(frame):
    """Return warnings for a usable table or raise for structural problems."""
    if not isinstance(frame, pd.DataFrame):
        raise ContractError("The uploaded object is not a tabular dataset.")
    if frame.shape[1] == 0:
        raise ContractError("The dataset must contain at least one column.")
    if frame.shape[0] == 0:
        raise ContractError("The dataset must contain at least one data row.")

    columns = list(frame.columns)
    blank = [str(column) for column in columns if str(column).strip() == ""]
    if blank:
        raise ContractError("Column names cannot be empty.")

    duplicates = []
    seen = set()
    for column in columns:
        if column in seen and column not in duplicates:
            duplicates.append(str(column))
        seen.add(column)
    if duplicates:
        raise ContractError(
            "Column names must be unique. Duplicates: " + ", ".join(duplicates)
        )

    warnings = []
    unnamed = [str(column) for column in columns if str(column).lower().startswith("unnamed:")]
    if unnamed:
        warnings.append(
            "Unnamed columns were retained; review them before analysis: "
            + ", ".join(unnamed)
        )

    empty_columns = [
        str(column) for column in columns
        if frame[column].isna().all()
    ]
    if empty_columns:
        warnings.append(
            "Columns contain no values: " + ", ".join(empty_columns)
        )
    return warnings


def validate_recipe(rules_data):
    """Validate recipe structure without touching a dataset."""
    from cpdm.core import recipes

    if not isinstance(rules_data, dict):
        raise ContractError("Cleaning file must contain a JSON object.")

    steps = rules_data.get("steps")
    if steps is not None and not isinstance(steps, list):
        raise ContractError("'steps' must be a list of operations.")

    if steps:
        for position, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ContractError(f"Step {position} is not an object.")
            operation = step.get("op")
            if operation not in recipes.OPERATIONS:
                raise ContractError(
                    f"Step {position} has an unknown operation '{operation}'."
                )
            if operation == recipes.OP_TEXT_RULES:
                if step.get("stage") not in (None, "headers", "values"):
                    raise ContractError(
                        f"Step {position} has an unknown text-rule stage."
                    )
                if not isinstance(step.get("rules", []), list):
                    raise ContractError(f"Step {position} rules must be a list.")
            elif operation in (recipes.OP_HEADER_MAP, recipes.OP_VALUE_REPLACEMENTS,
                               recipes.OP_EXACT_VALUES):
                if not isinstance(step.get("map", {}), dict):
                    raise ContractError(f"Step {position} map must be an object.")
    else:
        for key in ("header_map", "value_replacements"):
            if key in rules_data and not isinstance(rules_data[key], dict):
                raise ContractError(f"'{key}' must be an object.")
        if "ignored_columns" in rules_data and not isinstance(
            rules_data["ignored_columns"], list
        ):
            raise ContractError("'ignored_columns' must be a list.")

    return {"valid": True, "version": rules_data.get("version", 1)}
