import sqlite3
import pandas as pd
import json
import os
import re
from typing import Optional

DB_PATH = "data_assistant.db"
SCHEMA_PATH = "db_schema.json"


def get_connection():
    return sqlite3.connect(DB_PATH)


def sanitize_table_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if name and name[0].isdigit():
        name = "t_" + name
    return name or "uploaded_table"


def sanitize_column_name(col: str) -> str:
    col = re.sub(r"[^a-zA-Z0-9_]", "_", str(col))
    col = re.sub(r"_+", "_", col).strip("_").lower()
    if col and col[0].isdigit():
        col = "c_" + col
    return col or "column"


def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Run data quality checks on a DataFrame and return a profile report.
    Checks: nulls, duplicates, unique counts, data types, numeric stats.
    """
    total_rows = len(df)
    total_cols = len(df.columns)

    # ── Duplicate rows ───────────────────────────────────────────────────────
    duplicate_row_count = int(df.duplicated().sum())
    duplicate_row_pct = round(duplicate_row_count / total_rows * 100, 1) if total_rows else 0

    # ── Per-column profile ───────────────────────────────────────────────────
    columns = []
    issues = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        null_pct = round(null_count / total_rows * 100, 1) if total_rows else 0
        unique_count = int(series.nunique(dropna=True))
        duplicate_vals = int(total_rows - unique_count - null_count)
        dtype = str(series.dtype)

        col_profile = {
            "column": col,
            "dtype": dtype,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
            "duplicate_value_count": max(duplicate_vals, 0),
        }

        # Numeric stats
        if pd.api.types.is_numeric_dtype(series):
            col_profile.update({
                "min": round(float(series.min()), 4) if not series.isnull().all() else None,
                "max": round(float(series.max()), 4) if not series.isnull().all() else None,
                "mean": round(float(series.mean()), 4) if not series.isnull().all() else None,
                "std": round(float(series.std()), 4) if not series.isnull().all() else None,
            })

        # Top duplicate values (values appearing more than once)
        value_counts = series.value_counts()
        dupes = value_counts[value_counts > 1]
        if not dupes.empty:
            col_profile["top_duplicates"] = [
                {"value": str(v), "count": int(c)}
                for v, c in dupes.head(5).items()
            ]
        else:
            col_profile["top_duplicates"] = []

        columns.append(col_profile)

        # Flag issues
        if null_pct > 20:
            issues.append({"column": col, "issue": "high_nulls", "detail": f"{null_pct}% null values"})
        if unique_count == total_rows and total_rows > 1:
            issues.append({"column": col, "issue": "all_unique", "detail": "All values are unique (possible ID column)"})
        if unique_count == 1:
            issues.append({"column": col, "issue": "constant", "detail": "All values are identical"})
        if col_profile["top_duplicates"] and unique_count < total_rows * 0.1 and not pd.api.types.is_numeric_dtype(series):
            issues.append({"column": col, "issue": "low_cardinality", "detail": f"Only {unique_count} unique values"})

    if duplicate_row_count > 0:
        issues.insert(0, {
            "column": "— (entire row)",
            "issue": "duplicate_rows",
            "detail": f"{duplicate_row_count} duplicate rows ({duplicate_row_pct}%)"
        })

    return {
        "total_rows": total_rows,
        "total_columns": total_cols,
        "duplicate_row_count": duplicate_row_count,
        "duplicate_row_pct": duplicate_row_pct,
        "columns": columns,
        "issues": issues,
        "health_score": _compute_health_score(duplicate_row_count, total_rows, columns),
    }


def _compute_health_score(dup_rows: int, total_rows: int, columns: list) -> int:
    """Simple 0-100 health score based on nulls and duplicates."""
    score = 100
    if total_rows == 0:
        return 0

    # Penalise duplicate rows
    dup_pct = dup_rows / total_rows * 100
    score -= min(dup_pct * 2, 30)

    # Penalise null-heavy columns
    for col in columns:
        if col["null_pct"] > 50:
            score -= 10
        elif col["null_pct"] > 20:
            score -= 5

    return max(int(score), 0)


def ingest_file_to_db(filename: str, df: pd.DataFrame) -> dict:
    """Ingest a DataFrame into SQLite. Returns table info + quality profile."""
    table_name = sanitize_table_name(filename)

    df.columns = [sanitize_column_name(c) for c in df.columns]
    df = df.dropna(axis=1, how="all")

    # Run quality profile BEFORE writing to DB (on raw data)
    quality = profile_dataframe(df)

    with get_connection() as conn:
        df.to_sql(table_name, conn, if_exists="replace", index=False)

    schema = load_schema()
    schema[table_name] = {
        "source_file": filename,
        "columns": list(df.columns),
        "row_count": len(df),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
        "sample": df.head(3).to_dict(orient="records"),
        "quality": quality,
    }
    save_schema(schema)

    return schema[table_name]


def load_schema() -> dict:
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH) as f:
            return json.load(f)
    return {}


def save_schema(schema: dict):
    with open(SCHEMA_PATH, "w") as f:
        json.dump(schema, f, indent=2)


def get_schema_prompt() -> str:
    schema = load_schema()
    if not schema:
        return "No database tables available."

    lines = []
    for table, info in schema.items():
        lines.append(f"Table: {table}  (source: {info['source_file']}, {info['row_count']} rows)")
        for col in info["columns"]:
            dtype = info["dtypes"].get(col, "unknown")
            lines.append(f"  - {col}  [{dtype}]")
        if info.get("sample"):
            lines.append(f"  Sample row: {info['sample'][0]}")
        lines.append("")
    return "\n".join(lines)


def run_sql(sql: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def list_tables() -> list:
    schema = load_schema()
    return [
        {
            "table": t,
            "source_file": v["source_file"],
            "row_count": v["row_count"],
            "columns": v["columns"],
            "quality": v.get("quality"),
        }
        for t, v in schema.items()
    ]


def get_quality_report(table_name: str) -> dict:
    schema = load_schema()
    if table_name not in schema:
        return None

    with get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        df = df.replace([float('inf'), float('-inf')], None)
        df = df.where(pd.notnull(df), None)

    report = {"table": table_name, "row_count": len(df), "columns": {}, "issues": [], "duplicate_rows": 0}

    # Duplicate rows
    report["duplicate_rows"] = int(df.duplicated().sum())

    # Per column stats
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        unique_count = int(df[col].nunique())
        total = len(df)
        dup_values = df[col].dropna()
        dup_values = dup_values[dup_values.duplicated(keep=False)]
        top_dupes = dup_values.value_counts().head(5).to_dict()
        top_dupes = {str(k): int(v) for k, v in top_dupes.items()}

        issues = []
        if null_count / total > 0.2:
            issues.append("high_nulls")
        if unique_count == total:
            issues.append("all_unique")
        if unique_count == 1:
            issues.append("constant")
        if df[col].dtype == "object" and unique_count < 5:
            issues.append("low_cardinality")

        report["columns"][col] = {
            "null_count": null_count,
            "null_pct": round(float(null_count / total * 100), 1),
            "unique_count": unique_count,
            "duplicate_value_count": len(dup_values),
            "top_duplicate_values": top_dupes,
            "issues": issues,
        }

        report["issues"].extend([f"{col}: {i}" for i in issues])

    # Health score
    null_pct = sum(v["null_pct"] for v in report["columns"].values()) / len(df.columns)
    dup_pct = report["duplicate_rows"] / len(df) * 100
    report["health_score"] = max(0, round(100 - null_pct - dup_pct))

    return report