import requests
import pandas as pd
import json
import re
from typing import Optional
from database import ingest_file_to_db, get_quality_report


def flatten_json(obj, parent_key="", sep="_") -> dict:
    """Recursively flatten nested JSON into a flat dict."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, (dict, list)):
                items.update(flatten_json(v, new_key, sep))
            else:
                items[new_key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            if isinstance(v, (dict, list)):
                items.update(flatten_json(v, new_key, sep))
            else:
                items[new_key] = v
    else:
        items[parent_key] = obj
    return items


def extract_records(data) -> list:
    """
    Auto-detect where the array of records lives in a JSON response.
    Handles: top-level array, {data: [...]}, {results: [...]}, {items: [...]},
    {records: [...]}, {response: {data: [...]}}, etc.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Common keys that wrap arrays
        for key in ["data", "results", "items", "records", "content",
                    "entries", "rows", "list", "payload", "collection"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        # One level deeper
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                return v

        # Single object — wrap in list
        return [data]

    return []


def detect_next_page(response_json, response_headers, current_url: str, page_param: str, page_num: int) -> Optional[str]:
    """
    Detect pagination and return the next URL, or None if last page.
    Supports: Link header, next/nextPage/next_url fields, offset-based, page-based.
    """
    # Link header (GitHub style)
    link_header = response_headers.get("Link", "")
    if link_header:
        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if match:
            return match.group(1)

    # JSON body next link
    if isinstance(response_json, dict):
        for key in ["next", "next_page", "nextPage", "next_url", "nextUrl", "next_cursor"]:
            val = response_json.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                return val

        # Cursor-based
        cursor = response_json.get("cursor") or response_json.get("next_cursor")
        if cursor:
            sep = "&" if "?" in current_url else "?"
            return f"{current_url}{sep}cursor={cursor}"

    # Page-based — increment page param
    sep = "&" if "?" in current_url else "?"
    # Remove existing page param
    base = re.sub(rf"[&?]{page_param}=\d+", "", current_url)
    return f"{base}{sep}{page_param}={page_num + 1}"


def fetch_api_data(
    url: str,
    method: str = "GET",
    headers: dict = None,
    auth_type: str = "none",
    auth_token: str = None,
    api_key_header: str = None,
    api_key_value: str = None,
    body: dict = None,
    paginate: bool = False,
    max_pages: int = 5,
    page_param: str = "page",
    table_name: str = None,
) -> dict:
    """
    Full API ingestion pipeline:
    1. Fetch data (with auth + pagination)
    2. Flatten JSON → DataFrame
    3. Save to DuckDB
    4. Run quality check
    5. Return everything
    """
    # ── Build headers ─────────────────────────────────────────────────────────
    req_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    if auth_type == "bearer" and auth_token:
        req_headers["Authorization"] = f"Bearer {auth_token}"
    elif auth_type == "api_key" and api_key_header and api_key_value:
        req_headers[api_key_header] = api_key_value
    elif auth_type == "basic" and auth_token:
        import base64
        req_headers["Authorization"] = f"Basic {base64.b64encode(auth_token.encode()).decode()}"

    # ── Fetch pages ───────────────────────────────────────────────────────────
    all_records = []
    current_url = url
    pages_fetched = 0
    errors = []

    while current_url and pages_fetched < max_pages:
        try:
            if method.upper() == "POST":
                resp = requests.request(method, current_url, headers=req_headers,
                                        json=body, timeout=30)
            else:
                resp = requests.request(method, current_url, headers=req_headers, timeout=30)

            resp.raise_for_status()
            data = resp.json()

        except requests.exceptions.HTTPError as e:
            errors.append(f"HTTP {resp.status_code}: {str(e)}")
            break
        except requests.exceptions.Timeout:
            errors.append("Request timed out after 30 seconds")
            break
        except requests.exceptions.ConnectionError:
            errors.append(f"Could not connect to {current_url}")
            break
        except json.JSONDecodeError:
            errors.append("Response is not valid JSON")
            break
        except Exception as e:
            errors.append(str(e))
            break

        records = extract_records(data)
        if not records:
            if pages_fetched == 0:
                errors.append("Could not find an array of records in the response")
            break

        all_records.extend(records)
        pages_fetched += 1

        if not paginate or len(records) == 0:
            break

        # Detect next page
        next_url = detect_next_page(data, resp.headers, current_url, page_param, pages_fetched)
        if next_url == current_url or not next_url:
            break
        current_url = next_url

    if not all_records:
        return {
            "success": False,
            "error": errors[0] if errors else "No records found in API response",
            "pages_fetched": pages_fetched,
        }

    # ── Flatten → DataFrame ───────────────────────────────────────────────────
    flat_records = []
    for record in all_records:
        if isinstance(record, dict):
            flat_records.append(flatten_json(record))
        else:
            flat_records.append({"value": record})

    df = pd.DataFrame(flat_records)

    # Drop columns that are entirely None
    df = df.dropna(axis=1, how="all")

    # ── Ingest to DuckDB ──────────────────────────────────────────────────────
    source_name = table_name or _url_to_table_name(url)
    info = ingest_file_to_db(source_name, df)

    # ── Quality report ────────────────────────────────────────────────────────
    quality = get_quality_report(info["source_file"].replace(".csv", "").replace(".", "_").lower()
                                  if "." in info["source_file"] else info["source_file"])

    # Use the sanitized table name from info
    actual_table = list([k for k in [source_name] if k])[0]

    return {
        "success": True,
        "url": url,
        "pages_fetched": pages_fetched,
        "total_records": len(df),
        "columns": list(df.columns),
        "table_name": source_name,
        "sample": df.head(5).to_dict(orient="records"),
        "csv": df.to_csv(index=False),
        "quality": quality,
        "warnings": errors,
    }


def _url_to_table_name(url: str) -> str:
    """Convert a URL into a clean table name."""
    RESERVED = {"all", "select", "table", "from", "where", "order", "group",
                "by", "join", "index", "values", "set", "create", "drop",
                "insert", "update", "delete", "view", "with", "as", "on"}
    clean = re.sub(r"https?://", "", url)
    clean = clean.split("?")[0]
    parts = [p for p in clean.split("/") if p and not p.isdigit()]
    name = parts[-1] if parts else "api_data"
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    name = re.sub(r"_+", "_", name).strip("_")
    # If reserved word or empty, use second-to-last path segment or fallback
    if name in RESERVED or not name:
        name = parts[-2] if len(parts) >= 2 else "api_data"
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
        name = re.sub(r"_+", "_", name).strip("_")
        name = f"{name}_data" if name in RESERVED else name
    return name or "api_data"