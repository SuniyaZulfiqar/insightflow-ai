from pathlib import Path
from typing import Optional
from uuid import uuid4

import pandas as pd
import numpy as np
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _get_dataset(db: Session, dataset_id: int, workspace_id: int) -> Dataset:
    statement = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.workspace_id == workspace_id,
    )
    dataset = db.scalars(statement).first()

    if not dataset:
        raise ValueError("Dataset not found.")

    return dataset


def _load_dataframe(dataset: Dataset) -> pd.DataFrame:
    file_path = Path(dataset.file_path)

    if not file_path.exists():
        raise ValueError("Dataset file not found.")

    if dataset.file_type == "csv":
        return pd.read_csv(file_path)

    if dataset.file_type == "xlsx":
        return pd.read_excel(file_path, engine="openpyxl")

    if dataset.file_type == "xls":
        try:
            return pd.read_excel(file_path, engine="xlrd")
        except ImportError as exc:
            raise ValueError(
                "XLS support requires the xlrd package. Run: pip install xlrd"
            ) from exc

    raise ValueError("Unsupported dataset file type.")


def _is_date_like(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False

    sample = series.dropna().astype(str).head(100)

    if sample.empty:
        return False

    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return float(parsed.notna().mean()) >= 0.8


def _column_type(series: pd.Series) -> str:
    """Technical data type used by cleaning/profile logic."""
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    if _is_date_like(series):
        return "date"

    if (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or pd.api.types.is_categorical_dtype(series)
        or pd.api.types.is_bool_dtype(series)
    ):
        unique = series.nunique(dropna=True)
        return "categorical" if unique <= 20 else "text"

    return "text"


def _normalized_column_name(column: str) -> str:
    return (
        str(column)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _semantic_role(series: pd.Series, column: str) -> str:
    """
    Infer how a business analyst should treat the column.

    This is deliberately deterministic: the dashboard should make sensible
    decisions from the data itself instead of applying one chart rule to
    every column.
    """
    name = _normalized_column_name(column)
    unique = int(series.nunique(dropna=True))
    non_null = max(1, int(series.notna().sum()))
    uniqueness = unique / non_null

    identifier_tokens = (
        "id", "identifier", "uuid", "guid", "key", "code",
        "reference", "ref", "account_number", "account_no",
        "employee_number", "customer_number", "ticket_number",
        "phone", "postal", "zip", "zipcode"
    )
    measure_tokens = (
        "salary", "wage", "revenue", "sales", "amount", "price",
        "cost", "profit", "income", "expense", "budget", "value",
        "total", "subtotal", "tax", "discount", "balance", "payment",
        "quantity", "units", "count", "score", "rating", "hours"
    )
    dimension_tokens = (
        "age", "year", "month", "day", "rank", "level"
    )

    if _is_date_like(series):
        return "date"

    if any(
        token == name or name.endswith(f"_{token}") or f"_{token}_" in f"_{name}_"
        for token in identifier_tokens
    ):
        return "identifier"

    # A highly unique numeric field is usually an identifier even when its
    # name is not ideal (e.g. EmployeeNumber, RecordNo, database PKs).
    if pd.api.types.is_numeric_dtype(series) and uniqueness >= 0.98 and unique >= 10:
        return "identifier"

    if pd.api.types.is_numeric_dtype(series):
        if any(
            token == name or name.startswith(f"{token}_") or f"_{token}_" in f"_{name}_"
            for token in measure_tokens
        ):
            return "measure"

        if any(
            token == name or name.startswith(f"{token}_") or f"_{token}_" in f"_{name}_"
            for token in dimension_tokens
        ):
            return "numeric_dimension"

        # Low-cardinality numeric fields are dimensions (age, rating, year,
        # score bands, etc.) unless the column name clearly says it is a measure.
        if unique <= 30 or uniqueness <= 0.25:
            return "numeric_dimension"

        return "measure"

    if pd.api.types.is_bool_dtype(series):
        return "categorical"

    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        if unique <= 20:
            return "categorical"

        # Emails, names and other high-cardinality fields are useful as
        # dimensions/identifiers, but raw text should never become a 1,000-bar chart.
        if "email" in name or "name" in name or "username" in name:
            return "identifier"

        return "text"

    return "text"


def _safe_number(value):
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return round(float(value), 2)

    return value


def _json_safe(value):
    """Convert pandas/NumPy values into native JSON-serializable Python values."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _top_values(series: pd.Series, limit: int = 12) -> list[dict]:
    counts = series.fillna("Unknown").astype(str).value_counts().head(limit)
    return [
        {"label": str(label), "value": int(value)}
        for label, value in counts.items()
    ]


def get_datasets_for_workspace(
    db: Session,
    workspace_id: int,
) -> list[Dataset]:
    statement = (
        select(Dataset)
        .where(Dataset.workspace_id == workspace_id)
        .order_by(Dataset.created_at.desc())
    )

    return list(db.scalars(statement).all())


def save_dataset_file(
    db: Session,
    workspace_id: int,
    file: UploadFile,
) -> Dataset:
    """Validate, persist and register a CSV/XLSX/XLS upload."""
    original_filename = Path(file.filename or "").name
    if not original_filename:
        raise ValueError("Please choose a file to upload.")

    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only CSV, XLSX, and XLS files are supported.")

    if file.content_type and file.content_type not in {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }:
        raise ValueError("The selected file type does not match a supported dataset format.")

    stored_suffix = ".xlsx" if extension == ".xls" else extension
    stored_name = f"{workspace_id}_{uuid4().hex[:12]}_{Path(original_filename).stem}{stored_suffix}"
    file_path = UPLOAD_DIR / stored_name

    with file_path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)

    try:
        if extension == ".csv":
            try:
                dataframe = pd.read_csv(file_path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                dataframe = pd.read_csv(file_path, encoding="cp1252")
        elif extension == ".xlsx":
            dataframe = pd.read_excel(file_path, engine="openpyxl")
        else:
            try:
                dataframe = pd.read_excel(file_path, engine="xlrd")
            except ImportError as exc:
                raise ValueError(
                    "XLS files require xlrd. Run: pip install xlrd"
                ) from exc
    except ValueError:
        file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise ValueError(
            f"Could not read the uploaded {extension.lstrip('.').upper()} file. "
            f"It may be empty, corrupted, or invalid. Details: {exc}"
        ) from exc

    if dataframe.shape[1] == 0:
        file_path.unlink(missing_ok=True)
        raise ValueError("The uploaded dataset has no columns.")

    if dataframe.shape[0] == 0:
        file_path.unlink(missing_ok=True)
        raise ValueError("The uploaded dataset contains no data rows.")

    stored_file_type = "xlsx" if extension == ".xls" else extension.lstrip(".")
    if extension == ".xls":
        normalized_path = file_path.with_suffix(".xlsx")
        try:
            dataframe.to_excel(normalized_path, index=False, engine="openpyxl")
            file_path.unlink(missing_ok=True)
            file_path = normalized_path
        except Exception as exc:
            file_path.unlink(missing_ok=True)
            raise ValueError(f"The XLS file was readable but could not be converted to XLSX: {exc}") from exc

    dataset = Dataset(
        workspace_id=workspace_id,
        name=Path(original_filename).stem,
        filename=original_filename,
        file_type=stored_file_type,
        file_path=str(file_path),
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
    )

    try:
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return dataset


def delete_dataset(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> None:
    """Remove a dataset's stored file and its database record."""
    dataset = _get_dataset(db, dataset_id, workspace_id)

    file_path = Path(dataset.file_path)

    try:
        db.delete(dataset)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Best-effort cleanup: the DB record is the source of truth, so a file
    # that fails to delete should not roll back the already-committed delete.
    file_path.unlink(missing_ok=True)


def get_dataset_preview(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> dict:
    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    preview = dataframe.head(10).fillna("").astype(object).to_dict(orient="records")

    return {
        "id": dataset.id,
        "name": dataset.name,
        "filename": dataset.filename,
        "file_type": dataset.file_type,
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": [str(column) for column in dataframe.columns],
        "preview": preview,
    }


def _profile_column(dataframe: pd.DataFrame, column: str) -> dict:
    series = dataframe[column]
    kind = _column_type(series)
    role = _semantic_role(series, column)

    profile = {
        "name": str(column),
        "type": kind,
        "role": role,
        "dtype": str(series.dtype),
        "total": int(len(series)),
        "missing": int(series.isna().sum()),
        "missing_percentage": round(
            float(series.isna().mean() * 100), 2
        ) if len(series) else 0.0,
        "unique": int(series.nunique(dropna=True)),
    }

    if role in {"numeric_dimension", "measure", "identifier"} and pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
        profile["statistics"] = {
            "sum": _safe_number(numeric.sum()),
            "mean": _safe_number(numeric.mean()),
            "median": _safe_number(numeric.median()),
            "min": _safe_number(numeric.min()),
            "max": _safe_number(numeric.max()),
            "std": _safe_number(numeric.std()),
        }

    if role == "measure" and pd.api.types.is_numeric_dtype(series):
        profile["analysis"] = "measure"
        profile["recommended_aggregations"] = ["sum", "average", "median", "min", "max"]

    elif role == "numeric_dimension":
        profile["analysis"] = "distribution"
        profile["recommended_aggregations"] = ["count", "average", "median"]

    elif role == "identifier":
        profile["analysis"] = "unique_count"
        profile["recommended_aggregations"] = ["count", "unique_count"]

    elif kind == "categorical":
        profile["top_values"] = _top_values(series)
        profile["analysis"] = "category_distribution"

    elif kind == "text":
        text = series.dropna().astype(str)
        profile["analysis"] = "text_summary"
        profile["text_statistics"] = {
            "non_empty": int(text.shape[0]),
            "average_length": round(float(text.str.len().mean()), 2) if not text.empty else 0.0,
            "max_length": int(text.str.len().max()) if not text.empty else 0,
        }

    elif kind == "date":
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        profile["date_range"] = {
            "min": parsed.min().isoformat() if parsed.notna().any() else None,
            "max": parsed.max().isoformat() if parsed.notna().any() else None,
        }
        profile["analysis"] = "time_series"

    return profile


def get_dataset_analytics(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> dict:
    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    profiles = [
        _profile_column(dataframe, column)
        for column in dataframe.columns
    ]

    numeric_columns = [item for item in profiles if item["type"] == "numeric"]
    categorical_columns = [item for item in profiles if item["type"] == "categorical"]
    date_columns = [item for item in profiles if item["type"] == "date"]
    text_columns = [item for item in profiles if item["type"] == "text"]

    measure_columns = [
        item for item in numeric_columns if item.get("role") == "measure"
    ]
    numeric_dimension_columns = [
        item for item in numeric_columns if item.get("role") == "numeric_dimension"
    ]

    top_numeric = (
        max(measure_columns, key=lambda item: item["unique"])
        if measure_columns
        else (
            max(numeric_dimension_columns, key=lambda item: item["unique"])
            if numeric_dimension_columns
            else None
        )
    )

    top_categorical = (
        max(
            categorical_columns,
            key=lambda item: item["top_values"][0]["value"]
            if item.get("top_values")
            else 0,
        )
        if categorical_columns
        else None
    )

    return _json_safe({
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "total_rows": int(len(dataframe)),
        "total_columns": int(len(dataframe.columns)),
        "missing_values": {
            "count": int(dataframe.isna().sum().sum()),
            "percentage": round(
                float(dataframe.isna().sum().sum() / max(1, dataframe.size) * 100),
                2,
            ),
        },
        "duplicate_rows": int(dataframe.duplicated().sum()),
        "numeric_columns": len(numeric_columns),
        "measure_columns": len(measure_columns),
        "numeric_dimension_columns": len(numeric_dimension_columns),
        "identifier_columns": sum(1 for item in profiles if item.get("role") == "identifier"),
        "categorical_columns": len(categorical_columns),
        "date_columns": len(date_columns),
        "text_columns": len(text_columns),
        "top_numeric": top_numeric,
        "top_categorical": top_categorical,
        "columns": profiles,
    })


def get_dataset_statistics(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> dict:
    return get_dataset_analytics(db, dataset_id, workspace_id)


def _pick_group_column(dataframe: pd.DataFrame, target_column: str) -> Optional[str]:
    candidates = []

    for column in dataframe.columns:
        if column == target_column:
            continue

        series = dataframe[column]
        if _column_type(series) != "categorical":
            continue

        unique_count = series.nunique(dropna=True)

        if 2 <= unique_count <= 20:
            candidates.append(
                (
                    int(series.notna().sum()),
                    -int(unique_count),
                    str(column),
                )
            )

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][2]


def _fill_numeric_with_groups(
    dataframe: pd.DataFrame,
    column: str,
) -> tuple[pd.DataFrame, int, str]:
    before = int(dataframe[column].isna().sum())
    if before == 0:
        return dataframe, 0, "No missing values"

    group_column = _pick_group_column(dataframe, column)
    series = pd.to_numeric(dataframe[column], errors="coerce")

    if group_column:
        group_means = dataframe.assign(
            __target__=series
        ).groupby(group_column, dropna=False)["__target__"].transform("mean")
        series = series.fillna(group_means)

    global_mean = series.mean()

    if pd.notna(global_mean):
        series = series.fillna(global_mean)

    dataframe[column] = series
    after = int(dataframe[column].isna().sum())

    method = (
        f"group mean by {group_column}, then global mean"
        if group_column
        else "global mean"
    )

    return dataframe, before - after, method


def _fill_categorical_with_groups(
    dataframe: pd.DataFrame,
    column: str,
) -> tuple[pd.DataFrame, int, str]:
    before = int(dataframe[column].isna().sum())
    if before == 0:
        return dataframe, 0, "No missing values"

    group_column = _pick_group_column(dataframe, column)

    if group_column:
        helper = dataframe[[group_column, column]].copy()
        helper["__value__"] = helper[column].astype("object")

        group_modes = (
            helper.groupby(group_column, dropna=False)["__value__"]
            .agg(lambda values: values.dropna().mode().iloc[0]
                 if not values.dropna().mode().empty
                 else None)
        )

        mask = dataframe[column].isna()
        group_values = dataframe.loc[mask, group_column].map(group_modes)
        dataframe.loc[mask, column] = group_values

    global_mode = dataframe[column].dropna().mode()

    if not global_mode.empty:
        dataframe[column] = dataframe[column].fillna(global_mode.iloc[0])

    after = int(dataframe[column].isna().sum())

    method = (
        f"group mode by {group_column}, then global mode"
        if group_column
        else "global mode"
    )

    return dataframe, before - after, method


def _fill_date_values(
    dataframe: pd.DataFrame,
    column: str,
) -> tuple[pd.DataFrame, int, str]:
    before = int(dataframe[column].isna().sum())
    if before == 0:
        return dataframe, 0, "No missing values"

    parsed = pd.to_datetime(dataframe[column], errors="coerce", format="mixed")
    mode = parsed.dropna().mode()

    if mode.empty:
        return dataframe, 0, "No safe date replacement found"

    dataframe[column] = parsed.fillna(mode.iloc[0])
    after = int(dataframe[column].isna().sum())

    return dataframe, before - after, "date mode"


def get_dataset_quality(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> dict:
    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    missing_by_column = []
    suggested_repairs = []
    cleanable = 0

    for column in dataframe.columns:
        missing = int(dataframe[column].isna().sum())

        if missing == 0:
            continue

        kind = _column_type(dataframe[column])
        group_column = _pick_group_column(dataframe, column)

        if kind == "numeric":
            numeric = pd.to_numeric(dataframe[column], errors="coerce")
            safe = int(numeric.notna().sum()) > 0
            method = (
                f"group mean by {group_column}, then global mean"
                if group_column
                else "global mean"
            )
        elif kind == "categorical":
            safe = not dataframe[column].dropna().empty
            method = (
                f"group mode by {group_column}, then global mode"
                if group_column
                else "global mode"
            )
        elif kind == "text":
            safe = not dataframe[column].dropna().empty
            method = "global mode for text"
        elif kind == "date":
            safe = pd.to_datetime(
                dataframe[column], errors="coerce"
            ).notna().any()
            method = "date mode"
        else:
            safe = False
            method = "manual review"

        if safe:
            cleanable += missing

        missing_by_column.append(
            {
                "column": str(column),
                "type": kind,
                "missing": missing,
                "replaceable": bool(safe),
                "suggested_method": method,
            }
        )

        if safe:
            suggested_repairs.append(
                {
                    "column": str(column),
                    "missing": missing,
                    "method": method,
                }
            )

    duplicates = int(dataframe.duplicated().sum())

    return _json_safe({
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "total_rows": int(len(dataframe)),
        "total_columns": int(len(dataframe.columns)),
        "missing_values": {
            "count": int(dataframe.isna().sum().sum()),
            "columns": missing_by_column,
        },
        "duplicate_rows": duplicates,
        "cleanable_missing_values": int(cleanable),
        "suggested_repairs": suggested_repairs,
        "safe_to_clean": bool(cleanable > 0 or duplicates > 0),
    })


def clean_dataset(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    fill_missing: bool,
    remove_duplicates: bool,
) -> dict:
    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    original_rows = len(dataframe)
    original_missing = int(dataframe.isna().sum().sum())
    original_duplicates = int(dataframe.duplicated().sum())

    cleaned_missing_values = 0
    cleaning_actions = []

    if fill_missing:
        for column in dataframe.columns:
            if dataframe[column].isna().sum() == 0:
                continue

            kind = _column_type(dataframe[column])

            if kind == "numeric":
                dataframe, filled, method = _fill_numeric_with_groups(
                    dataframe, column
                )
            elif kind == "categorical":
                dataframe, filled, method = _fill_categorical_with_groups(
                    dataframe, column
                )
            elif kind == "text":
                dataframe, filled, method = _fill_categorical_with_groups(
                    dataframe, column
                )
                method = method.replace("global mode", "global mode for text")
            elif kind == "date":
                dataframe, filled, method = _fill_date_values(
                    dataframe, column
                )
            else:
                filled = 0
                method = "manual review"

            if filled:
                cleaned_missing_values += filled
                cleaning_actions.append(
                    {
                        "column": str(column),
                        "filled": int(filled),
                        "method": method,
                    }
                )

    removed_duplicate_rows = 0

    if remove_duplicates:
        before = len(dataframe)
        dataframe = dataframe.drop_duplicates().reset_index(drop=True)
        removed_duplicate_rows = before - len(dataframe)

        if removed_duplicate_rows:
            cleaning_actions.append(
                {
                    "action": "remove_duplicates",
                    "removed": int(removed_duplicate_rows),
                    "method": "exact duplicate row removal",
                }
            )

    file_path = Path(dataset.file_path)

    if dataset.file_type == "csv":
        dataframe.to_csv(file_path, index=False)
    elif dataset.file_type == "xlsx":
        dataframe.to_excel(file_path, index=False, engine="openpyxl")
    elif dataset.file_type == "xls":
        normalized_path = file_path.with_suffix(".xlsx")
        dataframe.to_excel(normalized_path, index=False, engine="openpyxl")
        file_path.unlink(missing_ok=True)
        dataset.file_path = str(normalized_path)
        dataset.file_type = "xlsx"
    else:
        raise ValueError("Unsupported dataset file type.")

    dataset.row_count = len(dataframe)
    dataset.column_count = len(dataframe.columns)

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "original_rows": int(original_rows),
        "final_rows": int(len(dataframe)),
        "original_missing_values": int(original_missing),
        "remaining_missing_values": int(dataframe.isna().sum().sum()),
        "cleaned_missing_values": int(cleaned_missing_values),
        "original_duplicate_rows": int(original_duplicates),
        "removed_duplicate_rows": int(removed_duplicate_rows),
        "remaining_duplicate_rows": int(dataframe.duplicated().sum()),
        "cleaning_actions": cleaning_actions,
    }



def build_cleaned_dataset_csv(
    db: Session,
    dataset_id: int,
    workspace_id: int,
) -> tuple[str, bytes]:
    """Return the currently persisted cleaned dataset as CSV bytes."""
    from io import StringIO

    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    output = StringIO()
    dataframe.to_csv(output, index=False)
    return "cleaned_data.csv", output.getvalue().encode("utf-8-sig")


def _format_metric(value) -> float | int | None:
    if pd.isna(value):
        return None
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


def _make_identifier_chart(series: pd.Series, column: str) -> dict:
    values = series.dropna()
    unique_count = int(values.nunique())
    return {
        "name": str(column),
        "type": "identifier",
        "role": "identifier",
        "chart": "summary",
        "unique_count": unique_count,
        "description": "Identifier field. Count and uniqueness are more meaningful than summing the identifier values.",
        "data": [
            {"label": "Records", "value": int(len(series))},
            {"label": "Unique", "value": unique_count},
            {"label": "Missing", "value": int(series.isna().sum())},
        ],
        "metric_label": "Count",
        "aggregation": "count",
    }


def _make_measure_chart(series: pd.Series, column: str) -> dict:
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return {
            "name": str(column),
            "type": "numeric",
            "role": "measure",
            "chart": "summary",
            "unique_count": 0,
            "description": "No numeric values available.",
            "data": [],
        }

    stats = [
        {"label": "Total", "value": _format_metric(numeric.sum())},
        {"label": "Average", "value": _format_metric(numeric.mean())},
        {"label": "Median", "value": _format_metric(numeric.median())},
        {"label": "Minimum", "value": _format_metric(numeric.min())},
        {"label": "Maximum", "value": _format_metric(numeric.max())},
    ]

    return {
        "name": str(column),
        "type": "numeric",
        "role": "measure",
        "chart": "summary",
        "unique_count": int(numeric.nunique()),
        "description": "Business measure summarized with appropriate statistical aggregations.",
        "data": stats,
        "metric_label": "Value",
        "aggregation": "sum + average + median + min + max",
    }


def _make_numeric_dimension_chart(series: pd.Series, column: str) -> dict:
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return {
            "name": str(column),
            "type": "numeric",
            "role": "numeric_dimension",
            "chart": "bar",
            "unique_count": 0,
            "description": "No numeric values available.",
            "data": [],
        }

    unique_count = int(numeric.nunique())

    if unique_count <= 30:
        counts = numeric.value_counts().sort_index()
        data = [
            {"label": _format_metric(label), "value": int(value)}
            for label, value in counts.items()
        ]
        description = "Frequency distribution. Numeric values are counted rather than incorrectly summed."
    else:
        bins = min(12, max(6, int(round(unique_count ** 0.5))))
        grouped = pd.cut(numeric, bins=bins, duplicates="drop").value_counts().sort_index()
        data = [
            {"label": str(interval), "value": int(value)}
            for interval, value in grouped.items()
        ]
        description = "Binned numeric distribution. Each bar shows how many records fall in the range."

    return {
        "name": str(column),
        "type": "numeric",
        "role": "numeric_dimension",
        "chart": "bar",
        "unique_count": unique_count,
        "description": description,
        "data": data,
        "metric_label": "Records",
        "aggregation": "count",
    }


def _make_categorical_chart(series: pd.Series, column: str) -> dict:
    counts = series.fillna("Unknown").astype(str).value_counts().head(12)

    data = [
        {"label": str(label), "value": int(value)}
        for label, value in counts.items()
    ]

    chart_type = "pie" if len(data) <= 8 else "bar"

    return {
        "name": str(column),
        "type": "categorical",
        "role": "categorical",
        "chart": chart_type,
        "unique_count": int(series.nunique(dropna=True)),
        "description": "Category distribution based on record counts.",
        "data": data,
        "metric_label": "Records",
        "aggregation": "count",
    }


def _make_text_summary_chart(series: pd.Series, column: str) -> dict:
    text = series.dropna().astype(str)
    return {
        "name": str(column),
        "type": "text",
        "role": "text",
        "chart": "summary",
        "unique_count": int(series.nunique(dropna=True)),
        "description": "Free-text summary. Raw text is not treated as a category for charting.",
        "data": [
            {"label": "Non-empty", "value": int(len(text))},
            {"label": "Unique", "value": int(series.nunique(dropna=True))},
            {"label": "Avg chars", "value": round(float(text.str.len().mean()), 1) if not text.empty else 0},
        ],
        "metric_label": "Value",
        "aggregation": "count + unique_count + average_length",
    }


def _make_date_chart(series: pd.Series, column: str) -> dict:
    parsed = pd.to_datetime(series, errors="coerce", format="mixed").dropna()

    if parsed.empty:
        return {
            "name": str(column),
            "type": "date",
            "role": "date",
            "chart": "bar",
            "unique_count": 0,
            "description": "No valid dates available.",
            "data": [],
        }

    grouped = (
        parsed.dt.to_period("M")
        .astype(str)
        .value_counts()
        .sort_index()
        .tail(24)
    )

    data = [
        {"label": str(label), "value": int(value)}
        for label, value in grouped.items()
    ]

    return {
        "name": str(column),
        "type": "date",
        "role": "date",
        "chart": "bar",
        "unique_count": int(parsed.nunique()),
        "description": "Records grouped by month.",
        "data": data,
        "metric_label": "Records",
        "aggregation": "count by month",
    }


def get_dataset_charts(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    columns: Optional[str] = None,
) -> dict:
    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    available = [str(column) for column in dataframe.columns]

    if columns:
        requested = [item.strip() for item in columns.split(",") if item.strip()]
        selected = [column for column in requested if column in available]
    else:
        selected = []

    if not selected:
        return _json_safe({
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "selected_columns": [],
            "charts": [],
            "message": "Select columns to generate the dashboard.",
        })

    charts = []

    for column in selected:
        series = dataframe[column]
        kind = _column_type(series)
        role = _semantic_role(series, column)

        if role == "identifier":
            charts.append(_make_identifier_chart(series, column))
        elif role == "measure":
            charts.append(_make_measure_chart(series, column))
        elif role == "numeric_dimension":
            charts.append(_make_numeric_dimension_chart(series, column))
        elif role == "categorical":
            charts.append(_make_categorical_chart(series, column))
        elif role == "date":
            charts.append(_make_date_chart(series, column))
        else:
            charts.append(_make_text_summary_chart(series, column))

    return _json_safe({
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "selected_columns": selected,
        "charts": charts,
    })

# ---------------------------------------------------------------------------
# Cleaning preview and PDF exports
# ---------------------------------------------------------------------------

def get_dataset_clean_preview(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    fill_missing: bool = True,
    remove_duplicates: bool = True,
) -> dict:
    """Build an in-memory before/after cleaning preview without saving changes."""
    dataset = _get_dataset(db, dataset_id, workspace_id)
    original = _load_dataframe(dataset).copy()
    proposed = original.copy()

    original_missing = int(original.isna().sum().sum())
    original_duplicates = int(original.duplicated().sum())
    filled_missing = 0
    removed_duplicates = 0
    actions = []

    if fill_missing:
        for column in proposed.columns:
            if proposed[column].isna().sum() == 0:
                continue

            kind = _column_type(proposed[column])
            if kind == "numeric":
                proposed, filled, method = _fill_numeric_with_groups(proposed, column)
            elif kind == "categorical":
                proposed, filled, method = _fill_categorical_with_groups(proposed, column)
            elif kind == "text":
                proposed, filled, method = _fill_categorical_with_groups(proposed, column)
                method = method.replace("global mode", "global mode for text")
            elif kind == "date":
                proposed, filled, method = _fill_date_values(proposed, column)
            else:
                filled, method = 0, "manual review"

            if filled:
                filled_missing += int(filled)
                actions.append({
                    "column": str(column),
                    "action": "fill_missing",
                    "filled": int(filled),
                    "affected": int(filled),
                    "method": method,
                })

    if remove_duplicates:
        before_rows = len(proposed)
        proposed = proposed.drop_duplicates().reset_index(drop=True)
        removed_duplicates = int(before_rows - len(proposed))
        if removed_duplicates:
            actions.append({
                "action": "remove_duplicates",
                "removed": removed_duplicates,
                "affected": removed_duplicates,
                "method": "exact duplicate row removal",
            })

    def records(frame: pd.DataFrame) -> list[dict]:
        return (
            frame.head(10)
            .fillna("")
            .astype(object)
            .to_dict(orient="records")
        )

    original_preview = records(original)
    proposed_preview = records(proposed)
    columns = [str(column) for column in original.columns]

    before = {
        "rows": int(len(original)),
        "missing_values": original_missing,
        "duplicate_rows": original_duplicates,
        "preview": original_preview,
    }
    after = {
        "rows": int(len(proposed)),
        "missing_values": int(proposed.isna().sum().sum()),
        "duplicate_rows": int(proposed.duplicated().sum()),
        "preview": proposed_preview,
    }

    changed_columns = []
    for column in original.columns:
        before_missing = int(original[column].isna().sum())
        after_missing = int(proposed[column].isna().sum())
        if before_missing != after_missing:
            changed_columns.append({
                "column": str(column),
                "missing_before": before_missing,
                "missing_after": after_missing,
                "filled": before_missing - after_missing,
            })

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "filename": dataset.filename,
        "file_type": dataset.file_type,
        "columns": columns,
        "requires_approval": bool(actions),
        "has_changes": bool(actions),
        "original_rows": int(len(original)),
        "preview_rows": int(len(proposed)),
        "final_rows": int(len(proposed)),
        "original_missing_values": original_missing,
        "preview_missing_values": int(proposed.isna().sum().sum()),
        "remaining_missing_values": int(proposed.isna().sum().sum()),
        "cleaned_missing_values": int(filled_missing),
        "original_duplicate_rows": original_duplicates,
        "preview_duplicate_rows": int(proposed.duplicated().sum()),
        "remaining_duplicate_rows": int(proposed.duplicated().sum()),
        "removed_duplicate_rows": removed_duplicates,
        "actions": actions,
        "cleaning_actions": actions,
        "changed_columns": changed_columns,
        "original_preview": original_preview,
        "cleaned_preview": proposed_preview,
        "before": before,
        "after": after,
    }


def _pdf_escape(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pdf_table_data(frame: pd.DataFrame, max_rows: int = 12) -> list[list]:
    rows = [[str(column) for column in frame.columns]]
    for _, row in frame.head(max_rows).iterrows():
        values = []
        for value in row.tolist():
            if pd.isna(value):
                values.append("")
            else:
                values.append(str(value)[:80])
        rows.append(values)
    return rows


def _build_pdf_document(title: str, output_path: str):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InsightFlowTitle", parent=styles["Title"], fontSize=20, leading=24,
        spaceAfter=8, textColor="#172554"
    )
    heading_style = ParagraphStyle(
        "InsightFlowHeading", parent=styles["Heading2"], fontSize=13, leading=16,
        spaceBefore=8, spaceAfter=6, textColor="#0f766e"
    )
    body_style = ParagraphStyle(
        "InsightFlowBody", parent=styles["BodyText"], fontSize=9, leading=12
    )
    document = SimpleDocTemplate(
        output_path, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm, title=title, author="InsightFlow AI"
    )
    return document, title_style, heading_style, body_style, Spacer, Paragraph, Table, TableStyle


def build_dataset_report_pdf(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    output_path: str | None = None,
) -> str:
    """Create the full dataset report as a real PDF file."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)
    analytics = get_dataset_analytics(db, dataset_id, workspace_id)
    quality = get_dataset_quality(db, dataset_id, workspace_id)

    if output_path is None:
        output_path = str(UPLOAD_DIR / f"{dataset.id}_report.pdf")

    document, title_style, heading_style, body_style, Spacer, Paragraph, Table, TableStyle = _build_pdf_document(
        f"InsightFlow AI - {dataset.name} Report", output_path
    )

    story = [
        Paragraph("InsightFlow AI — Dataset Report", title_style),
        Paragraph(
            f"<b>Dataset:</b> {_pdf_escape(dataset.name)}<br/>"
            f"<b>File:</b> {_pdf_escape(dataset.filename)}<br/>"
            f"<b>Rows:</b> {len(dataframe):,} &nbsp;&nbsp; <b>Columns:</b> {len(dataframe.columns):,}",
            body_style,
        ),
        Spacer(1, 10),
        Paragraph("Dataset Overview", heading_style),
    ]

    overview = [
        ["Metric", "Value"],
        ["Rows", f"{len(dataframe):,}"],
        ["Columns", f"{len(dataframe.columns):,}"],
        ["Missing values", f"{analytics['missing_values']['count']:,}"],
        ["Duplicate rows", f"{analytics['duplicate_rows']:,}"],
        ["Measures", str(analytics.get("measure_columns", 0))],
        ["Numeric dimensions", str(analytics.get("numeric_dimension_columns", 0))],
        ["Identifiers", str(analytics.get("identifier_columns", 0))],
        ["Categorical", str(analytics.get("categorical_columns", 0))],
        ["Date columns", str(analytics.get("date_columns", 0))],
    ]
    table = Table(overview, colWidths=[80 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.extend([table, Spacer(1, 10), Paragraph("Column Analysis", heading_style)])

    column_rows = [["Column", "Type", "Role", "Missing", "Unique", "Key analysis"]]
    for profile in analytics["columns"]:
        detail = profile.get("analysis", "")
        if profile.get("role") == "measure" and profile.get("statistics"):
            detail = f"Total {profile['statistics'].get('sum')} · Avg {profile['statistics'].get('mean')}"
        elif profile.get("role") == "numeric_dimension":
            detail = "Distribution / frequency"
        elif profile.get("role") == "identifier":
            detail = "Count + unique count"
        elif profile.get("role") == "categorical":
            detail = "Category distribution"
        elif profile.get("role") == "date":
            detail = "Records by month"
        column_rows.append([
            str(profile["name"]), str(profile["type"]), str(profile.get("role", "")),
            str(profile["missing"]), str(profile["unique"]), detail,
        ])

    column_table = Table(column_rows, repeatRows=1)
    column_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([column_table, Spacer(1, 12), Paragraph("Data Quality", heading_style)])
    story.append(Paragraph(
        f"Missing values detected: {quality['missing_values']['count']:,}<br/>"
        f"Fillable values: {quality['cleanable_missing_values']:,}<br/>"
        f"Duplicate rows: {quality['duplicate_rows']:,}", body_style
    ))

    if quality.get("suggested_repairs"):
        repair_rows = [["Column", "Missing", "Suggested method"]]
        for repair in quality["suggested_repairs"]:
            repair_rows.append([str(repair["column"]), str(repair["missing"]), str(repair["method"])])
        repair_table = Table(repair_rows, repeatRows=1)
        repair_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7C3AED")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story.extend([Spacer(1, 7), repair_table])

    story.extend([Spacer(1, 12), Paragraph("Data Preview", heading_style)])
    preview = _pdf_table_data(dataframe, max_rows=12)
    preview_table = Table(preview, repeatRows=1)
    preview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 5.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(preview_table)

    document.build(story)
    return output_path



def build_cleaned_data_pdf(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    output_path: str | None = None,
) -> str:
    """Create a real PDF containing the current persisted (cleaned) dataset."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    if output_path is None:
        output_path = str(UPLOAD_DIR / f"{dataset.id}_cleaned_data.pdf")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InsightFlowCleanedTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=7,
        textColor=colors.HexColor("#172554"),
    )
    cell_style = ParagraphStyle(
        "InsightFlowCleanedCell",
        parent=styles["BodyText"],
        fontSize=5.6,
        leading=7,
        spaceAfter=0,
        spaceBefore=0,
    )
    header_style = ParagraphStyle(
        "InsightFlowCleanedHeader",
        parent=cell_style,
        fontSize=5.8,
        leading=7,
        textColor=colors.white,
    )

    document = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"InsightFlow AI - {dataset.name} Cleaned Data",
        author="InsightFlow AI",
    )

    story = [
        Paragraph("InsightFlow AI — Cleaned Dataset", title_style),
        Paragraph(
            f"<b>Dataset:</b> {_pdf_escape(dataset.name)} &nbsp;&nbsp; "
            f"<b>Rows:</b> {len(dataframe):,} &nbsp;&nbsp; "
            f"<b>Columns:</b> {len(dataframe.columns):,}",
            cell_style,
        ),
    ]

    columns = [str(column) for column in dataframe.columns]
    table_rows = [[Paragraph(_pdf_escape(column), header_style) for column in columns]]
    for row in dataframe.itertuples(index=False, name=None):
        table_rows.append([
            Paragraph(
                _pdf_escape("" if pd.isna(value) else str(value)[:160]),
                cell_style,
            )
            for value in row
        ])

    usable_width = 281 * mm
    col_width = usable_width / max(len(columns), 1)
    table = LongTable(
        table_rows,
        colWidths=[col_width] * len(columns),
        repeatRows=1,
        splitByRow=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(table)
    document.build(story)
    return output_path

def build_dashboard_pdf(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    columns: Optional[str] = None,
    output_path: str | None = None,
) -> str:
    """Create a PDF containing the selected dashboard analytics."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    dataset = _get_dataset(db, dataset_id, workspace_id)
    analytics = get_dataset_analytics(db, dataset_id, workspace_id)
    charts_result = get_dataset_charts(db, dataset_id, workspace_id, columns=columns)

    if output_path is None:
        output_path = str(UPLOAD_DIR / f"{dataset.id}_dashboard.pdf")

    document, title_style, heading_style, body_style, Spacer, Paragraph, Table, TableStyle = _build_pdf_document(
        f"InsightFlow AI - {dataset.name} Dashboard", output_path
    )

    story = [
        Paragraph("InsightFlow AI — Analytics Dashboard", title_style),
        Paragraph(
            f"<b>Dataset:</b> {_pdf_escape(dataset.name)}<br/>"
            f"<b>Total records:</b> {analytics['total_rows']:,}<br/>"
            f"<b>Total columns:</b> {analytics['total_columns']:,}", body_style
        ),
        Spacer(1, 10),
    ]

    kpis = [
        ["Total Rows", "Columns", "Missing Values", "Duplicates"],
        [
            f"{analytics['total_rows']:,}",
            f"{analytics['total_columns']:,}",
            f"{analytics['missing_values']['count']:,}",
            f"{analytics['duplicate_rows']:,}",
        ],
    ]
    kpi_table = Table(kpis, colWidths=[40 * mm] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EFF6FF")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#172554")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([kpi_table, Spacer(1, 12), Paragraph("Selected Analytics", heading_style)])

    charts = charts_result.get("charts", [])
    if not charts:
        story.append(Paragraph("No dashboard columns were selected.", body_style))
    else:
        for chart in charts:
            story.append(Paragraph(_pdf_escape(chart.get("name", "Chart")), heading_style))
            story.append(Paragraph(_pdf_escape(chart.get("description", "")), body_style))
            rows = [["Category / Metric", "Value"]]
            for item in chart.get("data", []):
                rows.append([_pdf_escape(item.get("label")), _pdf_escape(item.get("value"))])
            chart_table = Table(rows, repeatRows=1)
            chart_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.extend([chart_table, Spacer(1, 10)])

    document.build(story)
    return output_path



def build_cleaned_dataset_pdf(
    db: Session,
    dataset_id: int,
    workspace_id: int,
    output_path: str | None = None,
) -> str:
    """Create a PDF containing the currently persisted (already cleaned) dataset."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    dataset = _get_dataset(db, dataset_id, workspace_id)
    dataframe = _load_dataframe(dataset)

    if output_path is None:
        output_path = str(UPLOAD_DIR / f"{dataset.id}_cleaned.pdf")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InsightFlowCleanedTitle", parent=styles["Title"], fontSize=18, leading=22,
        spaceAfter=6, textColor="#172554",
    )
    body_style = ParagraphStyle(
        "InsightFlowCleanedBody", parent=styles["BodyText"], fontSize=8, leading=10,
    )
    cell_style = ParagraphStyle(
        "InsightFlowCleanedCell", parent=styles["BodyText"], fontSize=5.5, leading=6.5, wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "InsightFlowCleanedHeader", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold",
    )

    document = SimpleDocTemplate(
        output_path, pagesize=landscape(A4), rightMargin=8 * mm, leftMargin=8 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
        title=f"InsightFlow AI - {dataset.name} Cleaned Data", author="InsightFlow AI",
    )

    columns = [str(column) for column in dataframe.columns]
    rows = [[Paragraph(column, header_style) for column in columns]]
    for row in dataframe.itertuples(index=False, name=None):
        values = []
        for value in row:
            text = "" if pd.isna(value) else str(value)
            values.append(Paragraph(_pdf_escape(text), cell_style))
        rows.append(values)

    available_width = 297 * mm - 16 * mm
    column_width = available_width / max(1, len(columns))
    table = LongTable(rows, repeatRows=1, colWidths=[column_width] * len(columns), splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    story = [
        Paragraph("InsightFlow AI — Cleaned Dataset", title_style),
        Paragraph(
            f"<b>Dataset:</b> {_pdf_escape(dataset.name)} &nbsp;&nbsp; "
            f"<b>Rows:</b> {len(dataframe):,} &nbsp;&nbsp; "
            f"<b>Columns:</b> {len(dataframe.columns):,}", body_style,
        ),
        Spacer(1, 8),
        table,
    ]

    document.build(story)
    return output_path
