import pandas as pd
import numpy as np
from database import get_connection, load_schema


def compare_tables(table_a: str, table_b: str, key_column: str = None) -> dict:
    """
    Full reconciliation report between two DuckDB tables.
    Returns row counts, column overlap, value match rates, and mismatches.
    """
    schema = load_schema()

    if table_a not in schema:
        return {"success": False, "error": f"Table '{table_a}' not found"}
    if table_b not in schema:
        return {"success": False, "error": f"Table '{table_b}' not found"}

    with get_connection() as conn:
        df_a = conn.execute(f"SELECT * FROM {table_a}").df()
        df_b = conn.execute(f"SELECT * FROM {table_b}").df()

    result = {
        "success": True,
        "table_a": table_a,
        "table_b": table_b,
        "key_column": key_column,
        "row_counts": {},
        "column_overlap": {},
        "value_comparison": {},
        "row_level": {},
        "mismatches": [],
    }

    # ── Row counts ────────────────────────────────────────────────────────────
    result["row_counts"] = {
        "table_a": len(df_a),
        "table_b": len(df_b),
        "difference": len(df_a) - len(df_b),
        "match": len(df_a) == len(df_b),
    }

    # ── Column overlap ────────────────────────────────────────────────────────
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    shared_cols = cols_a & cols_b
    only_in_a = cols_a - cols_b
    only_in_b = cols_b - cols_a

    result["column_overlap"] = {
        "shared": sorted(list(shared_cols)),
        "only_in_a": sorted(list(only_in_a)),
        "only_in_b": sorted(list(only_in_b)),
        "total_a": len(cols_a),
        "total_b": len(cols_b),
        "shared_count": len(shared_cols),
        "overlap_pct": round(len(shared_cols) / max(len(cols_a), len(cols_b)) * 100, 1),
    }

    if not shared_cols:
        result["summary"] = "No shared columns — tables have completely different schemas."
        return result

    # ── Exact duplicate rows between files ────────────────────────────────────
    shared = sorted(list(shared_cols))
    df_a_shared = df_a[shared].astype(str).fillna("NULL")
    df_b_shared = df_b[shared].astype(str).fillna("NULL")

    # Rows in A that also exist in B (on shared columns)
    merged = df_a_shared.merge(df_b_shared, on=shared, how="inner")
    rows_in_both = len(merged)
    rows_only_in_a = len(df_a_shared) - rows_in_both
    rows_only_in_b = len(df_b_shared) - rows_in_both

    result["row_level"] = {
        "rows_in_both": rows_in_both,
        "rows_only_in_a": rows_only_in_a,
        "rows_only_in_b": rows_only_in_b,
        "exact_match_pct": round(rows_in_both / max(len(df_a), len(df_b)) * 100, 1) if max(len(df_a), len(df_b)) > 0 else 0,
    }

    # ── Per-column value comparison on shared cols ────────────────────────────
    min_rows = min(len(df_a), len(df_b))
    col_stats = {}

    for col in shared:
        a_vals = df_a[col].astype(str).fillna("NULL").reset_index(drop=True)
        b_vals = df_b[col].astype(str).fillna("NULL").reset_index(drop=True)

        # Compare positionally up to min_rows
        a_slice = a_vals[:min_rows]
        b_slice = b_vals[:min_rows]

        matches = (a_slice == b_slice).sum()
        match_pct = round(matches / min_rows * 100, 1) if min_rows > 0 else 0.0

        # Unique values in each
        unique_a = set(a_vals.unique())
        unique_b = set(b_vals.unique())
        values_only_in_a = unique_a - unique_b
        values_only_in_b = unique_b - unique_a

        col_stats[col] = {
            "match_count": int(matches),
            "mismatch_count": int(min_rows - matches),
            "match_pct": match_pct,
            "unique_values_a": len(unique_a),
            "unique_values_b": len(unique_b),
            "values_only_in_a": sorted([str(v) for v in list(values_only_in_a)[:10]]),
            "values_only_in_b": sorted([str(v) for v in list(values_only_in_b)[:10]]),
            "status": "✅ Match" if match_pct == 100 else ("⚠️ Partial" if match_pct >= 80 else "❌ Mismatch"),
        }

    result["value_comparison"] = col_stats

    # ── Key-based row diff ────────────────────────────────────────────────────
    if key_column and key_column in shared_cols:
        df_a_keyed = df_a[shared].set_index(key_column)
        df_b_keyed = df_b[shared].set_index(key_column)

        keys_only_in_a = set(df_a_keyed.index) - set(df_b_keyed.index)
        keys_only_in_b = set(df_b_keyed.index) - set(df_a_keyed.index)
        common_keys = set(df_a_keyed.index) & set(df_b_keyed.index)

        # For common keys, find rows where any value differs
        mismatches = []
        for key in list(common_keys)[:100]:  # cap at 100 for performance
            row_a = df_a_keyed.loc[key].astype(str)
            row_b = df_b_keyed.loc[key].astype(str)
            diff_cols = [c for c in row_a.index if row_a[c] != row_b[c]]
            if diff_cols:
                mismatches.append({
                    "key": str(key),
                    "differing_columns": diff_cols,
                    "values_a": {c: str(row_a[c]) for c in diff_cols},
                    "values_b": {c: str(row_b[c]) for c in diff_cols},
                })

        result["key_analysis"] = {
            "key_column": key_column,
            "common_keys": len(common_keys),
            "keys_only_in_a": sorted([str(k) for k in list(keys_only_in_a)[:20]]),
            "keys_only_in_b": sorted([str(k) for k in list(keys_only_in_b)[:20]]),
            "rows_with_differences": len(mismatches),
            "mismatch_details": mismatches[:50],  # cap display at 50
        }

    # ── Overall summary score ─────────────────────────────────────────────────
    avg_match = (
        sum(v["match_pct"] for v in col_stats.values()) / len(col_stats)
        if col_stats else 0
    )
    result["overall_match_pct"] = round(avg_match, 1)
    result["verdict"] = (
        "✅ Tables are identical" if avg_match == 100 and result["row_counts"]["match"]
        else "⚠️ Minor differences found" if avg_match >= 90
        else "❌ Significant differences found"
    )

    return result