"""Operational safeguards for uploads, jobs, and versioned documents."""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
import tempfile

from cpdm.core.contracts import ContractError


@dataclass(frozen=True)
class UploadPolicy:
    """Bound upload size and extension before a reader is invoked."""

    max_bytes: int = 50 * 1024 * 1024
    extensions: tuple[str, ...] = (".csv", ".tsv", ".xlsx", ".xlsm")

    def validate(self, filename, size):
        suffix = Path(filename or "").suffix.lower()
        if suffix not in self.extensions:
            raise ContractError(f"Unsupported upload extension '{suffix}'.")
        if size < 0 or size > self.max_bytes:
            raise ContractError(
                f"Upload exceeds the {self.max_bytes} byte size limit."
            )
        return True

    def validate_storage(self, file_storage):
        """Validate a Flask-like uploaded file without consuming its stream."""
        stream = file_storage.stream
        position = stream.tell()
        try:
            stream.seek(0, 2)
            size = stream.tell()
        finally:
            stream.seek(position)
        return self.validate(getattr(file_storage, "filename", ""), size)


class SafeTemporaryDirectory:
    """Create a private temporary directory and expose only resolved children."""

    def __init__(self, prefix="cpdm-"):
        self._directory = tempfile.TemporaryDirectory(prefix=prefix)
        self.path = Path(self._directory.name)

    def child(self, name):
        candidate = (self.path / name).resolve()
        if self.path not in candidate.parents:
            raise ContractError("Temporary path escapes its working directory.")
        return candidate

    def cleanup(self):
        self._directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cleanup()


class JobRegistry:
    """Small in-process job state store for future background executors."""

    def __init__(self):
        self._jobs = {}
        self._lock = Lock()

    def create(self, operation):
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id, "operation": operation, "status": "queued",
                "progress": 0, "error": None, "result": None,
            }
        return job_id

    def update(self, job_id, *, status=None, progress=None, error=None, result=None):
        with self._lock:
            if job_id not in self._jobs:
                raise ContractError(f"Unknown job '{job_id}'.")
            job = self._jobs[job_id]
            if status is not None:
                job["status"] = status
            if progress is not None:
                if not 0 <= progress <= 100:
                    raise ContractError("Job progress must be between 0 and 100.")
                job["progress"] = progress
            if error is not None:
                job["error"] = str(error)
            if result is not None:
                job["result"] = result

    def get(self, job_id):
        with self._lock:
            if job_id not in self._jobs:
                raise ContractError(f"Unknown job '{job_id}'.")
            return dict(self._jobs[job_id])


class JobExecutor:
    """Run bounded in-process jobs while exposing registry-backed progress."""

    def __init__(self, registry=None, max_workers=1):
        self.registry = registry or JobRegistry()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures = {}

    def submit(self, operation, function, *args, **kwargs):
        job_id = self.registry.create(operation)

        def execute():
            self.registry.update(job_id, status="running")
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                self.registry.update(job_id, status="failed", error=exc)
                return
            self.registry.update(job_id, status="completed", progress=100, result=result)

        self._futures[job_id] = self._executor.submit(execute)
        return job_id

    def wait(self, job_id, timeout=None):
        """Wait for a submitted job and return its final registry snapshot."""
        future = self._futures.get(job_id)
        if future is None:
            raise ContractError(f"Unknown job '{job_id}'.")
        future.result(timeout=timeout)
        return self.registry.get(job_id)

    def shutdown(self):
        self._executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()


def run_with_timeout(function, timeout, *args, **kwargs):
    """Run a callable and raise ``TimeoutError`` when it exceeds a limit."""
    if timeout <= 0:
        raise ContractError("Timeout must be greater than zero.")
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(function, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        future.cancel()
        raise TimeoutError(f"Operation exceeded the {timeout} second timeout.") from None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class VersionedDocument:
    """Validate and migrate JSON documents through explicit schema versions."""

    def __init__(self, kind, version, migrations=()):
        self.kind = kind
        self.version = version
        self.migrations = dict(migrations)

    def load(self, payload):
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict) or payload.get("kind") != self.kind:
            raise ContractError(f"Expected a '{self.kind}' document.")
        current = int(payload.get("version", 1))
        value = dict(payload)
        while current < self.version:
            migration = self.migrations.get(current)
            if migration is None:
                raise ContractError(
                    f"No migration exists from {self.kind} version {current}."
                )
            value = migration(value)
            current += 1
            value["version"] = current
        if current != self.version:
            raise ContractError(
                f"Unsupported {self.kind} version {current}; expected {self.version}."
            )
        return value
