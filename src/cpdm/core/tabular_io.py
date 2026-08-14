"""Reading and writing the working table (.xlsx / .csv)."""

import io
import os

import pandas as pd

EXCEL_EXTENSIONS = (".xlsx", ".xlsm")
CSV_EXTENSIONS = (".csv", ".tsv", ".txt")
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS + CSV_EXTENSIONS

EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIMETYPE = "text/csv"


def _extension(filename):
    return os.path.splitext(filename or "")[1].lower()


def read_table(file_storage):
    """Read an uploaded file into a dataframe, picking the reader by extension."""
    ext = _extension(getattr(file_storage, "filename", ""))
    if ext in EXCEL_EXTENSIONS:
        return pd.read_excel(file_storage)
    if ext in CSV_EXTENSIONS:
        sep = "\t" if ext == ".tsv" else ","
        return pd.read_csv(file_storage, sep=sep)
    raise ValueError(
        f"Unsupported file type '{ext or 'unknown'}'. "
        f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def load_into(dataset, file_storage):
    """Read an upload and make it the working dataset."""
    df = read_table(file_storage)
    return dataset.load(df, getattr(file_storage, "filename", None))


def export(dataset, fmt="xlsx"):
    """Serialise the working dataframe. Returns (stream, filename, mimetype)."""
    df = dataset.require_df()
    stem = os.path.splitext(dataset.filename)[0]
    fmt = (fmt or "xlsx").lower()

    if fmt == "csv":
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return (
            io.BytesIO(buffer.getvalue().encode("utf-8-sig")),
            f"processed_{stem}.csv",
            CSV_MIMETYPE,
        )

    if fmt != "xlsx":
        raise ValueError(f"Unsupported export format '{fmt}'. Use 'xlsx' or 'csv'.")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Processed_Data")
    output.seek(0)
    return output, f"processed_{stem}.xlsx", EXCEL_MIMETYPE
