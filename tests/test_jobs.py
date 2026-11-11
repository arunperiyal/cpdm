import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, jobs, operations  # noqa: E402


def test_named_core_jobs_use_serializable_executor_specs():
    with operations.JobExecutor() as executor:
        job_id = jobs.submit_core_job(
            executor, "report", {"format": "json"}, lambda payload: payload["format"]
        )
        assert executor.wait(job_id)["result"] == "json"
    with pytest.raises(contracts.ContractError, match="Unsupported"):
        jobs.submit_core_job(executor, "unknown", {}, lambda payload: payload)
