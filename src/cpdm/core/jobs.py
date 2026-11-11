"""Serializable job entry points for expensive core operations."""

from cpdm.core.contracts import ContractError
from cpdm.core.operations import JobExecutor, JobSpec


OPERATIONS = {"scoring", "reliability", "bootstrap", "report"}


def submit_core_job(executor, operation, payload, function):
    """Submit one named core operation through the shared executor boundary."""
    if operation not in OPERATIONS:
        raise ContractError(f"Unsupported core job operation '{operation}'.")
    spec = JobSpec(operation, payload)
    return executor.submit_spec(spec, function)
