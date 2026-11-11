"""Validated participant/dyad keys, reshaping, and derived variables."""

from dataclasses import dataclass
import re

import pandas as pd

from cpdm.core.contracts import ContractError


@dataclass(frozen=True)
class ParticipantKey:
    """Stable participant identity and its dyad membership."""

    participant_id: str
    dyad_id: str
    role_code: str

    @classmethod
    def parse(cls, value, pattern=r"^(?P<dyad_id>\d+)(?P<role_code>[A-Za-z]+)$"):
        match = re.match(pattern, str(value))
        if not match:
            raise ContractError(f"Participant ID '{value}' does not match the key pattern.")
        return cls(
            participant_id=str(value),
            dyad_id=match.group("dyad_id"),
            role_code=match.group("role_code"),
        )


@dataclass(frozen=True)
class DyadKey:
    """Stable identity for a participant pair or other grouped unit."""

    value: str


@dataclass(frozen=True)
class RoleDefinition:
    """Allowed partner roles and their display labels."""

    roles: dict[str, str]
    required: tuple[str, ...] | None = None

    def __post_init__(self):
        if not self.roles:
            raise ContractError("At least one partner role is required.")
        required = self.required or tuple(self.roles)
        unknown = set(required) - set(self.roles)
        if unknown:
            raise ContractError(
                "Required roles are not defined: " + ", ".join(sorted(unknown))
            )
        object.__setattr__(self, "required", tuple(required))

    def validate(self, values):
        unknown = sorted(set(values.dropna().astype(str)) - set(self.roles))
        if unknown:
            raise ContractError("Unknown partner role(s): " + ", ".join(unknown))

    def label(self, role):
        try:
            return self.roles[role]
        except KeyError:
            raise ContractError(f"Unknown partner role '{role}'.") from None


@dataclass
class DyadTable:
    """A participant table with explicit dyad and role invariants."""

    frame: pd.DataFrame
    dyad_column: str
    role_column: str
    participant_column: str | None = None
    role_definition: RoleDefinition | None = None

    def validate(self):
        required = [self.dyad_column, self.role_column]
        if self.participant_column:
            required.append(self.participant_column)
        missing = [column for column in required if column not in self.frame.columns]
        if missing:
            raise ContractError("Missing dyad column(s): " + ", ".join(missing))

        if self.frame[required].isna().any().any():
            raise ContractError("Dyad identifiers and roles cannot be missing.")
        if self.role_definition:
            self.role_definition.validate(self.frame[self.role_column])

        if self.participant_column and self.frame[self.participant_column].duplicated().any():
            duplicate = self.frame.loc[
                self.frame[self.participant_column].duplicated(keep=False),
                self.participant_column,
            ].astype(str).unique()
            raise ContractError("Duplicate participant ID(s): " + ", ".join(duplicate))

        duplicate_roles = self.frame.duplicated(
            [self.dyad_column, self.role_column], keep=False
        )
        if duplicate_roles.any():
            pairs = self.frame.loc[
                duplicate_roles, [self.dyad_column, self.role_column]
            ].drop_duplicates()
            formatted = [f"{row[0]}:{row[1]}" for row in pairs.itertuples(index=False)]
            raise ContractError("Duplicate dyad role record(s): " + ", ".join(formatted))

        counts = self.frame.groupby(self.dyad_column, dropna=False)[self.role_column].nunique()
        if self.role_definition:
            expected = len(self.role_definition.required)
            incomplete = counts[counts != expected]
        else:
            incomplete = counts[counts < 2]
        if not incomplete.empty:
            ids = ", ".join(map(str, incomplete.index))
            raise ContractError("Incomplete dyad(s): " + ids)

        return self

    def diagnostics(self):
        try:
            self.validate()
        except ContractError as exc:
            return {"valid": False, "error": str(exc)}
        counts = self.frame.groupby(self.dyad_column).size()
        return {
            "valid": True,
            "dyads": int(counts.size),
            "participants": int(len(self.frame)),
            "roles": sorted(self.frame[self.role_column].astype(str).unique()),
            "rows_per_dyad": sorted(counts.unique().tolist()),
            "analysis_columns": self.analysis_columns(),
        }

    def analysis_columns(self):
        excluded = {self.dyad_column, self.role_column}
        if self.participant_column:
            excluded.add(self.participant_column)
        return [column for column in self.frame.columns if column not in excluded]


@dataclass(frozen=True)
class ReshapePlan:
    """A deterministic long/wide mapping for validated dyad data."""

    dyad_column: str
    role_column: str
    value_columns: tuple[str, ...] | None = None
    id_columns: tuple[str, ...] = ()
    name_template: str = "{column}_{role_initial}"
    role_definition: RoleDefinition | None = None

    def _roles(self, frame):
        values = list(dict.fromkeys(frame[self.role_column].astype(str)))
        if self.role_definition:
            self.role_definition.validate(frame[self.role_column])
            return list(self.role_definition.required)
        return values

    def _name(self, column, role):
        return self.name_template.format(
            column=column,
            role=role,
            role_initial=role[:1].lower(),
        )

    def _ids(self):
        return tuple(dict.fromkeys((self.dyad_column, *self.id_columns)))

    def to_wide(self, frame):
        table = DyadTable(
            frame,
            self.dyad_column,
            self.role_column,
            role_definition=self.role_definition,
        ).validate()
        ids = self._ids()
        values = list(self.value_columns or table.analysis_columns())
        unknown = sorted(set(values) - set(frame.columns))
        if unknown:
            raise ContractError("Unknown reshape column(s): " + ", ".join(unknown))

        generated = [self._name(column, role) for column in values for role in self._roles(frame)]
        if len(generated) != len(set(generated)) or set(generated) & set(ids):
            raise ContractError("Reshape would create duplicate or identifier columns.")

        index = frame.set_index([*ids, self.role_column])
        wide_values = index[values].unstack(self.role_column)
        rows = wide_values.reset_index()
        rows.columns = [
            column[0]
            if isinstance(column, tuple) and len(column) >= 2 and column[1] == ""
            else (
                self._name(column[0], str(column[1]))
                if isinstance(column, tuple)
                else column
            )
            for column in rows.columns
        ]
        return rows

    def to_long(self, frame):
        ids = self._ids()
        roles = list(self.role_definition.required) if self.role_definition else None
        values = list(self.value_columns or [])
        if not values:
            suffixes = {}
            for column in frame.columns:
                for role in roles or []:
                    name = self._name(column, role)
                    if name in frame.columns:
                        suffixes.setdefault(column, []).append(role)
            values = list(suffixes)
        if not values:
            raise ContractError("to_long needs value_columns or a role definition.")

        records = []
        for role in roles or []:
            source = {column: self._name(column, role) for column in values}
            missing = [name for name in source.values() if name not in frame.columns]
            if missing:
                raise ContractError("Wide table is missing column(s): " + ", ".join(missing))
            for _, row in frame.iterrows():
                record = {column: row[column] for column in ids}
                record[self.role_column] = role
                record.update({column: row[name] for column, name in source.items()})
                records.append(record)
        return pd.DataFrame(records, columns=[*ids, self.role_column, *values])


@dataclass(frozen=True)
class DerivedVariable:
    """Create one actor/partner or cross-partner derived column."""

    name: str
    operation: str
    column: str
    role: str | None = None
    partner_role: str | None = None
    other: str | None = None

    def apply(self, frame, name_template="{column}_{role_initial}"):
        def role_column(base, role):
            if role is None:
                raise ContractError(f"{self.operation} requires a role.")
            name = name_template.format(
                column=base, role=role, role_initial=role[:1].lower()
            )
            if name not in frame.columns:
                raise ContractError(f"Missing derived-variable source column '{name}'.")
            return frame[name]

        if self.operation == "actor":
            value = role_column(self.column, self.role)
        elif self.operation == "partner":
            value = role_column(self.column, self.partner_role)
        elif self.operation in {"difference", "mean", "interaction"}:
            left = role_column(self.column, self.role)
            right = role_column(self.other or self.column, self.partner_role)
            if self.operation == "difference":
                value = left - right
            elif self.operation == "mean":
                value = pd.concat([left, right], axis=1).mean(axis=1)
            else:
                value = left * right
        else:
            raise ContractError(f"Unknown derived-variable operation '{self.operation}'.")

        result = frame.copy()
        if self.name in result.columns:
            raise ContractError(f"Derived column '{self.name}' already exists.")
        result[self.name] = value
        return result
