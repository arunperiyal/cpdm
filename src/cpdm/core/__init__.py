"""Core layer: dataframe state and transformations, with no Flask imports.

Every module here takes a :class:`cpdm.core.dataset.Dataset` as its first
argument, which keeps the transformations unit-testable without a request.
"""
