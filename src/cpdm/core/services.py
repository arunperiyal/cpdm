"""Application services that keep file/session orchestration out of routes."""

from cpdm.core import results, tabular_io
from cpdm.core.contracts import validate_dataframe
from cpdm.core.operations import UploadPolicy


class DatasetService:
    """Coordinate I/O and a dataset without owning the dataset itself."""

    def __init__(self, dataset, upload_policy=None):
        self.dataset = dataset
        self.upload_policy = upload_policy or UploadPolicy()

    def load(self, file_storage):
        self.upload_policy.validate_storage(file_storage)
        frame = tabular_io.read_table(file_storage)
        warnings = validate_dataframe(frame)
        loaded = self.dataset.load(frame, getattr(file_storage, "filename", None))
        return results.OperationResult(
            "load",
            changed=True,
            warnings=warnings,
            provenance={"source_filename": getattr(file_storage, "filename", None)},
            details=loaded,
        ).as_dict()

    def export(self, fmt="xlsx"):
        return tabular_io.export(self.dataset, fmt)
