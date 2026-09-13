import re
import json
from groq import Groq
import os

GROQ_MODEL = "llama-3.3-70b-versatile"

def chat(prompt: str) -> str:
    from dotenv import load_dotenv
    load_dotenv()
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
import pandas as pd
import numpy as np
from typing import Optional
from database import get_schema_prompt, run_sql, load_schema

from dotenv import load_dotenv
load_dotenv()


def extract_sql(text: str) -> Optional[str]:
    """Extract the first SQL SELECT statement from LLM output."""
    fenced = re.search(r"```(?:sql)?\s*(SELECT[\s\S]+?)```", text, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    bare = re.search(r"(SELECT[\s\S]+?)(;|$)", text, re.IGNORECASE)
    if bare:
        return bare.group(1).strip()

    return None


def detect_tables_used(sql: str) -> list:
    """Extract table names referenced in a SQL query."""
    schema = load_schema()
    used = []
    sql_lower = sql.lower()
    for table in schema.keys():
        if table.lower() in sql_lower:
            used.append(table)
    return used


def infer_join_keys(schema: dict) -> str:
    """
    Scan all tables and suggest likely join keys based on shared column names.
    Returns a hint string injected into the LLM prompt.
    """
    # Build map: column_name -> [table1, table2, ...]
    col_to_tables: dict = {}
    for table, info in schema.items():
        for col in info["columns"]:
            col_to_tables.setdefault(col, []).append(table)

    hints = []
    for col, tables in col_to_tables.items():
        if len(tables) >= 2:
            pairs = []
            for i in range(len(tables)):
                for j in range(i + 1, len(tables)):
                    pairs.append(f"{tables[i]}.{col} = {tables[j]}.{col}")
            hints.append(f"  - Shared column `{col}`: " + ", ".join(pairs))

    if not hints:
        return "No obvious shared columns detected — use your best judgment for joins."

    return "Likely join keys based on shared column names:\n" + "\n".join(hints)


def determine_chart_type(question: str, df: pd.DataFrame) -> str:
    q = question.lower()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cols = list(df.columns)

    if any(w in q for w in ["trend", "over time", "monthly", "daily", "weekly", "yearly", "by year", "by month"]):
        return "line"
    if any(w in q for w in ["distribution", "spread", "histogram"]):
        return "histogram"
    if any(w in q for w in ["proportion", "share", "percentage", "breakdown", "pie"]):
        return "pie"
    if any(w in q for w in ["scatter", "correlation", "vs", "versus", "relationship"]):
        return "scatter"
    if len(cols) >= 2 and len(numeric_cols) >= 1:
        return "bar"
    return "table"


def generate_chart_config(df: pd.DataFrame, chart_type: str, question: str) -> dict:
    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = [c for c in cols if c not in numeric_cols]

    x_col = categorical_cols[0] if categorical_cols else cols[0]
    y_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])

    config = {
        "chart_type": chart_type,
        "x": x_col,
        "y": y_col,
        "all_columns": cols,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "title": question,
    }

    if chart_type == "scatter" and len(numeric_cols) >= 2:
        config["y"] = numeric_cols[1]

    if chart_type == "pie":
        config["names"] = x_col
        config["values"] = y_col

    return config


def answer_data_question(question: str) -> dict:
    schema = load_schema()
    schema_str = get_schema_prompt()

    if not schema or schema_str == "No database tables available.":
        return {
            "success": False,
            "error": "No data tables uploaded yet. Please upload a CSV or Excel file first.",
        }

    join_hints = infer_join_keys(schema)
    table_count = len(schema)

    # Build an ultra-explicit schema block listing every column per table
    explicit_schema_lines = []
    for table_name, info in schema.items():
        cols = info["columns"]
        explicit_schema_lines.append(f"TABLE: {table_name}")
        explicit_schema_lines.append(f"  COLUMNS (use ONLY these): {', '.join(cols)}")
        if info.get("sample"):
            explicit_schema_lines.append(f"  SAMPLE ROW: {info['sample'][0]}")
        explicit_schema_lines.append("")
    explicit_schema = "\n".join(explicit_schema_lines)

    sql_prompt = f"""You are a SQLite expert. Write a single valid SQLite SELECT query to answer the user's question.

STRICT RULES — violating any rule will cause an error:
1. Return ONLY a ```sql ... ``` code block. No prose, no explanation.
2. ONLY use table names and column names EXACTLY as listed in the schema below. Do NOT invent columns.
3. Before referencing any column, verify it exists in the schema.
4. When joining tables, only join on columns that exist in BOTH tables.
5. Always prefix column names with the table name or alias (e.g. orders.amount, NOT just amount).
6. Do NOT use subquery aliases as if they were real tables.
7. Use aggregate functions (SUM, AVG, COUNT) where appropriate.
8. Limit to 100 rows.

AVAILABLE TABLES AND COLUMNS:
{explicit_schema}

{join_hints}

Question: {question}

Think step by step:
- Which tables are needed?
- Which exact columns exist in those tables?
- Is a JOIN needed? If so, what is the shared column?
- Write the query using ONLY those columns.
"""

    raw_sql_text = chat(sql_prompt)
    sql = extract_sql(raw_sql_text)

    if not sql:
        return {
            "success": False,
            "error": "Could not extract a valid SQL query from the model response.",
            "raw_response": raw_sql_text,
        }

    try:
        df = run_sql(sql)
    except Exception as e:
        # Send the error back to the LLM for one self-correction attempt
        fix_prompt = f"""This SQLite query failed. Fix it.

ERROR: {str(e)}

FAILED QUERY:
```sql
{sql}
```

AVAILABLE TABLES AND COLUMNS (use ONLY these exact names):
{explicit_schema}

Rules:
- Return ONLY the corrected SQL inside a ```sql ... ``` block.
- Do NOT use any column or table name that is not listed above.
- Prefix every column with its table name or alias.
- No explanation."""

        fixed_sql = extract_sql(chat(fix_prompt))

        if not fixed_sql:
            return {"success": False, "error": f"SQL execution failed and could not be auto-fixed: {str(e)}", "sql": sql}

        try:
            df = run_sql(fixed_sql)
            sql = fixed_sql  # use the fixed version going forward
        except Exception as e2:
            return {"success": False, "error": f"SQL failed after auto-fix attempt: {str(e2)}", "sql": fixed_sql}

    tables_used = detect_tables_used(sql)

    if df.empty:
        return {
            "success": True,
            "sql": sql,
            "chart_type": "table",
            "data": [],
            "chart_config": {},
            "tables_used": tables_used,
            "insight": "The query returned no results.",
        }

    chart_type = determine_chart_type(question, df)
    chart_config = generate_chart_config(df, chart_type, question)

    # Generate insight
    data_summary = df.head(5).to_string(index=False)
    insight_prompt = f"""Given this data result, write one concise insight sentence (max 30 words) for a business user.

Question: {question}
Data (first 5 rows):
{data_summary}

Respond with ONLY the insight sentence."""

    insight_text = chat(insight_prompt)

    return {
        "success": True,
        "sql": sql,
        "chart_type": chart_type,
        "chart_config": chart_config,
        "data": df.to_dict(orient="records"),
        "columns": list(df.columns),
        "tables_used": tables_used,
        "insight": insight_text,
        "join_used": len(tables_used) > 1,
    }