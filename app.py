import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(
    page_title="AI Document & Data Assistant",
    page_icon="🧠",
    layout="wide",
)

API_URL = "http://127.0.0.1:8000"

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }

    div[data-testid="stTabs"] button {
        font-size: 0.9rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    .insight-box {
        background: #f0f7ff;
        border-left: 4px solid #2563eb;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 1rem;
        font-size: 0.95rem;
        color: #1e3a5f;
    }

    .join-badge {
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        margin-bottom: 0.75rem;
        font-size: 0.88rem;
        color: #92400e;
        font-weight: 600;
    }

    .table-pill {
        display: inline-block;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.78rem;
        font-weight: 700;
        margin: 2px 3px;
        font-family: monospace;
    }

    .source-pill {
        display: inline-block;
        background: #e0e7ff;
        color: #3730a3;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.78rem;
        font-weight: 600;
        margin: 2px 3px;
    }

    .quality-score-good { background:#dcfce7; color:#166534; border-radius:8px; padding:6px 14px; font-weight:700; font-size:1.1rem; display:inline-block; }
    .quality-score-warn { background:#fef9c3; color:#854d0e; border-radius:8px; padding:6px 14px; font-weight:700; font-size:1.1rem; display:inline-block; }
    .quality-score-bad  { background:#fee2e2; color:#991b1b; border-radius:8px; padding:6px 14px; font-weight:700; font-size:1.1rem; display:inline-block; }
    .issue-row { padding:4px 0; border-bottom:1px solid #f3f4f6; font-size:0.85rem; }
    .sql-label {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #6b7280;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }

    div[data-testid="stFileUploader"] {
        border: 1.5px dashed #d1d5db;
        border-radius: 8px;
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Document & Data Assistant")
st.caption("Ask questions across documents · Visualize structured data · Multi-table joins · Powered by local LLM")
st.divider()

tab_docs, tab_data, tab_quality = st.tabs(["📄 Document Q&A", "📊 Data Analysis", "🔍 Data Quality"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Document Q&A
# ══════════════════════════════════════════════════════════════════════════════
with tab_docs:
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.subheader("Upload Documents")
        uploaded_files = st.file_uploader(
            "PDF or TXT files",
            accept_multiple_files=True,
            type=["txt", "pdf"],
            key="doc_uploader",
        )

        if st.button("⬆️ Upload & Index", use_container_width=True):
            if uploaded_files:
                files = [("files", (f.name, f, f.type)) for f in uploaded_files]
                with st.spinner("Indexing…"):
                    res = requests.post(f"{API_URL}/upload", files=files)
                if res.status_code == 200:
                    d = res.json()
                    st.success(f"Indexed {d['new_chunks_added']} new chunks ({d['total_chunks']} total)")
                else:
                    st.error(res.text)
            else:
                st.warning("Select at least one file.")

        st.divider()
        st.subheader("Indexed Documents")
        if st.button("↻ Refresh", use_container_width=True, key="refresh_docs"):
            res = requests.get(f"{API_URL}/documents")
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                if docs:
                    for doc in docs:
                        st.markdown(f"<span class='source-pill'>📄 {doc}</span>", unsafe_allow_html=True)
                else:
                    st.info("No documents uploaded yet.")

    with right:
        st.subheader("Ask a Question")
        question = st.text_input("Question", placeholder="e.g. What are the key findings?", label_visibility="collapsed")

        if st.button("🔍 Get Answer", use_container_width=True):
            if question.strip():
                with st.spinner("Searching & generating…"):
                    res = requests.post(f"{API_URL}/ask", json={"question": question})

                if res.status_code == 200:
                    data = res.json()
                    st.markdown("#### Answer")
                    st.write(data["answer"])
                    st.markdown("#### Sources")
                    for src in data.get("sources", []):
                        st.markdown(f"<span class='source-pill'>📄 {src}</span>", unsafe_allow_html=True)
                    with st.expander("🔎 Rewritten query & retrieved chunks"):
                        st.code(data.get("rewritten_question", ""), language="text")
                        for i, chunk in enumerate(data.get("context_used", []), 1):
                            st.markdown(f"**Chunk {i}**")
                            st.write(chunk)
                            st.markdown("---")
                elif res.status_code == 400:
                    st.warning(res.json().get("detail", "Upload a document first."))
                else:
                    st.error(res.text)
            else:
                st.warning("Enter a question first.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Data Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab_data:
    d_left, d_right = st.columns([1, 2], gap="large")

    # ── Left panel ────────────────────────────────────────────────────────────
    with d_left:
        st.subheader("Upload Data Files")
        st.caption("CSV and Excel files. Each file becomes a queryable table. Upload multiple files to enable joins.")

        data_files = st.file_uploader(
            "CSV or Excel files",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls"],
            key="data_uploader",
        )

        if st.button("⬆️ Upload to Database", use_container_width=True):
            if data_files:
                files = [("files", (f.name, f, f.type)) for f in data_files]
                with st.spinner("Ingesting into database…"):
                    res = requests.post(f"{API_URL}/upload-data", files=files)

                if res.status_code == 200:
                    for r in res.json().get("results", []):
                        if r["status"] == "success":
                            st.success(f"✅ **{r['file']}** → `{r['rows']}` rows, {len(r['columns'])} columns")
                        elif r["status"] == "skipped":
                            st.warning(f"⚠️ {r['file']}: {r['reason']}")
                        else:
                            st.error(f"❌ {r['file']}: {r['reason']}")
                else:
                    st.error(res.text)
            else:
                st.warning("Select at least one CSV or Excel file.")

        st.divider()
        st.subheader("Available Tables")

        if st.button("↻ Refresh tables", use_container_width=True, key="refresh_tables"):
            res = requests.get(f"{API_URL}/data-tables")
            if res.status_code == 200:
                tables = res.json().get("tables", [])
                if tables:
                    # Show join hint if multiple tables share column names
                    if len(tables) > 1:
                        all_cols = {}
                        for t in tables:
                            for col in t["columns"]:
                                all_cols.setdefault(col, []).append(t["table"])
                        shared = {col: tbls for col, tbls in all_cols.items() if len(tbls) > 1}
                        if shared:
                            hint_lines = [f"`{col}` → shared by: {', '.join(tbls)}" for col, tbls in shared.items()]
                            st.info("🔗 **Joinable columns detected:**\n\n" + "\n\n".join(hint_lines))

                    for t in tables:
                        with st.expander(f"🗄️ `{t['table']}` — {t['row_count']} rows"):
                            st.caption(f"Source: {t['source_file']}")
                            for col in t["columns"]:
                                st.markdown(f"- `{col}`")
                else:
                    st.info("No data tables yet.")

    # ── Right panel ───────────────────────────────────────────────────────────
    with d_right:
        st.subheader("Ask a Data Question")
        st.caption("Ask anything — including questions that span multiple tables. The AI detects joins automatically.")

        example_questions = [
            "Show total sales by department as a bar chart",
            "What are the top 5 employees by total orders placed?",
            "Show average order value per customer region",
            "Which department has the highest revenue this year?",
            "Show monthly trend of orders joined with employee data",
        ]

        selected_example = st.selectbox(
            "Try an example",
            [""] + example_questions,
            label_visibility="collapsed",
            format_func=lambda x: "💡 Pick an example question…" if x == "" else x,
        )

        data_question = st.text_input(
            "Your question",
            value=selected_example,
            placeholder="e.g. Show total revenue by region joining orders and customers",
            label_visibility="collapsed",
        )

        chart_override = st.selectbox(
            "Chart type override (optional)",
            ["Auto-detect", "bar", "line", "pie", "scatter", "histogram", "table"],
        )

        if st.button("📊 Generate Chart", use_container_width=True):
            if data_question.strip():
                with st.spinner("Writing SQL, running query, building chart…"):
                    res = requests.post(f"{API_URL}/analyze", json={"question": data_question})

                if res.status_code == 200:
                    result = res.json()

                    # ── Join badge ──────────────────────────────────────────
                    tables_used = result.get("tables_used", [])
                    if result.get("join_used"):
                        pills = "".join([f"<span class='table-pill'>{t}</span>" for t in tables_used])
                        st.markdown(
                            f"<div class='join-badge'>🔗 Join detected across {len(tables_used)} tables: {pills}</div>",
                            unsafe_allow_html=True,
                        )
                    elif tables_used:
                        pills = "".join([f"<span class='table-pill'>{t}</span>" for t in tables_used])
                        st.markdown(
                            f"<div style='margin-bottom:0.75rem;font-size:0.85rem;color:#6b7280;'>Table used: {pills}</div>",
                            unsafe_allow_html=True,
                        )

                    # ── Insight ─────────────────────────────────────────────
                    if result.get("insight"):
                        st.markdown(
                            f"<div class='insight-box'>💡 {result['insight']}</div>",
                            unsafe_allow_html=True,
                        )

                    # ── Result ──────────────────────────────────────────────
                    data_records = result.get("data", [])
                    chart_config = result.get("chart_config", {})
                    chart_type = (
                        chart_override if chart_override != "Auto-detect"
                        else result.get("chart_type", "bar")
                    )

                    if not data_records:
                        st.info("The query returned no results.")
                    else:
                        df = pd.DataFrame(data_records)
                        numeric_cols = df.select_dtypes(include="number").columns.tolist()
                        all_cols = list(df.columns)

                        # Decide: show table only when chart_type is table,
                        # or when there are no numeric columns to chart,
                        # or when the question implies listing/showing records
                        listing_keywords = ["list", "show me", "give me", "what are", "display", "which", "who", "all"]
                        is_listing = any(w in data_question.lower() for w in listing_keywords)
                        force_table = chart_type == "table" or not numeric_cols or (is_listing and len(all_cols) > 2)

                        if force_table:
                            # ── Interactive styled table ─────────────────────
                            st.markdown(f"**{len(df)} rows · {len(all_cols)} columns**")
                            st.dataframe(
                                df,
                                use_container_width=True,
                                height=min(400, 38 + len(df) * 35),
                                column_config={
                                    col: st.column_config.NumberColumn(format="%.2f")
                                    if col in numeric_cols else st.column_config.TextColumn()
                                    for col in all_cols
                                },
                            )

                            # Also offer a chart if there's plottable data
                            if numeric_cols and len(all_cols) >= 2:
                                with st.expander("📊 Also view as chart"):
                                    cat_cols = [c for c in all_cols if c not in numeric_cols]
                                    x_col = cat_cols[0] if cat_cols else all_cols[0]
                                    y_col = numeric_cols[0]
                                    fig = px.bar(
                                        df, x=x_col, y=y_col,
                                        title=data_question,
                                        color=x_col,
                                        color_discrete_sequence=px.colors.qualitative.Bold,
                                        template="plotly_white",
                                    )
                                    fig.update_layout(showlegend=False, height=380, margin=dict(t=50, l=20, r=20, b=20))
                                    st.plotly_chart(fig, use_container_width=True)
                        else:
                            # ── Chart ────────────────────────────────────────
                            x = chart_config.get("x")
                            y = chart_config.get("y")
                            title = data_question
                            fig = None

                            if chart_type == "bar":
                                fig = px.bar(
                                    df, x=x, y=y, title=title,
                                    color=x,
                                    color_discrete_sequence=px.colors.qualitative.Bold,
                                    template="plotly_white",
                                )
                                fig.update_layout(showlegend=False)

                            elif chart_type == "line":
                                fig = px.line(
                                    df, x=x, y=y, title=title,
                                    markers=True,
                                    template="plotly_white",
                                    color_discrete_sequence=["#2563eb"],
                                )

                            elif chart_type == "pie":
                                fig = px.pie(
                                    df,
                                    names=chart_config.get("names", x),
                                    values=chart_config.get("values", y),
                                    title=title,
                                    color_discrete_sequence=px.colors.qualitative.Bold,
                                    template="plotly_white",
                                )

                            elif chart_type == "scatter":
                                color_col = (
                                    chart_config["categorical_columns"][0]
                                    if chart_config.get("categorical_columns") else None
                                )
                                fig = px.scatter(
                                    df, x=x, y=y, title=title,
                                    color=color_col,
                                    template="plotly_white",
                                )

                            elif chart_type == "histogram":
                                fig = px.histogram(
                                    df, x=x, title=title,
                                    template="plotly_white",
                                    color_discrete_sequence=["#2563eb"],
                                )

                            if fig:
                                fig.update_layout(
                                    title_font_size=15,
                                    margin=dict(t=50, l=20, r=20, b=20),
                                    height=420,
                                )
                                st.plotly_chart(fig, use_container_width=True)

                            # Always show data table below the chart
                            with st.expander("📋 View as table"):
                                st.dataframe(
                                    df,
                                    use_container_width=True,
                                    height=min(400, 38 + len(df) * 35),
                                    column_config={
                                        col: st.column_config.NumberColumn(format="%.2f")
                                        if col in numeric_cols else st.column_config.TextColumn()
                                        for col in all_cols
                                    },
                                )

                        # ── Download button ──────────────────────────────────
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label="⬇️ Download results as CSV",
                            data=csv,
                            file_name="query_results.csv",
                            mime="text/csv",
                        )

                    # ── SQL ─────────────────────────────────────────────────
                    with st.expander("🔧 Generated SQL"):
                        st.markdown("<div class='sql-label'>SQLite Query</div>", unsafe_allow_html=True)
                        st.code(result.get("sql", ""), language="sql")

                elif res.status_code == 422:
                    st.error(f"❌ {res.json().get('detail', 'Analysis failed.')}")
                else:
                    st.error(res.text)
            else:
                st.warning("Enter a question or pick an example above.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Data Quality
# ══════════════════════════════════════════════════════════════════════════════
with tab_quality:
    st.subheader("Data Quality Report")
    st.caption("Checks for nulls, duplicates, and column-level issues across uploaded tables.")

    res = requests.get(f"{API_URL}/data-tables")
    if res.status_code != 200 or not res.json().get("tables"):
        st.info("Upload a CSV or Excel file in the Data Analysis tab first.")
    else:
        tables = res.json()["tables"]
        selected_table = st.selectbox("Select a table to inspect", [t["table"] for t in tables])

        if st.button("🔍 Run Quality Check", use_container_width=True):
            qres = requests.get(f"{API_URL}/quality/{selected_table}")
            if qres.status_code == 200:
                q = qres.json()
                # q structure: {table, row_count, duplicate_rows, health_score, columns: {col_name: {null_count, null_pct, unique_count, duplicate_value_count, top_duplicate_values, issues}}, issues: [str]}

                # ── Top metrics ───────────────────────────────────────────
                score = q.get("health_score", 0)
                score_emoji = "✅" if score >= 80 else ("⚠️" if score >= 50 else "❌")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Health Score", f"{score_emoji} {score}/100")
                c2.metric("Total Rows", f"{q['row_count']:,}")
                c3.metric("Duplicate Rows", f"{q['duplicate_rows']:,}",
                          delta=f"-{q['duplicate_rows']}" if q['duplicate_rows'] > 0 else None,
                          delta_color="inverse")
                c4.metric("Columns", len(q.get("columns", {})))

                # ── Issues summary ────────────────────────────────────────
                issues = q.get("issues", [])
                if issues:
                    st.markdown("#### ⚠️ Issues Found")
                    for issue in issues:
                        st.warning(f"⚠️ {issue}")
                else:
                    st.success("✅ No issues detected — data looks clean!")

                st.divider()

                # ── Column profile table ──────────────────────────────────
                st.markdown("#### Column Profile")
                col_data = []
                for col_name, stats in q.get("columns", {}).items():
                    top_dupes = stats.get("top_duplicate_values", {})
                    dupe_preview = ", ".join([f"{k} (×{v})" for k, v in list(top_dupes.items())[:3]]) if top_dupes else "—"
                    col_data.append({
                        "Column": col_name,
                        "Nulls": f"{stats['null_count']} ({stats['null_pct']}%)",
                        "Unique": stats["unique_count"],
                        "Duplicates": stats["duplicate_value_count"],
                        "Top Duplicate Values": dupe_preview,
                        "Issues": ", ".join(stats.get("issues", [])) or "—",
                    })

                profile_df = pd.DataFrame(col_data)
                st.dataframe(profile_df, use_container_width=True, hide_index=True)

                # ── Duplicate value drilldown ─────────────────────────────
                st.markdown("#### Duplicate Value Drilldown")
                cols_with_dupes = {
                    col_name: stats["top_duplicate_values"]
                    for col_name, stats in q.get("columns", {}).items()
                    if stats.get("top_duplicate_values")
                }

                if cols_with_dupes:
                    selected_col = st.selectbox("Pick a column to inspect", list(cols_with_dupes.keys()))
                    top_dupes = cols_with_dupes[selected_col]
                    dupe_df = pd.DataFrame(list(top_dupes.items()), columns=["Value", "Count"])
                    fig = px.bar(
                        dupe_df, x="Value", y="Count",
                        title=f"Duplicate values in '{selected_col}'",
                        color="Value",
                        color_discrete_sequence=px.colors.qualitative.Bold,
                        template="plotly_white",
                    )
                    fig.update_layout(showlegend=False, height=350, margin=dict(t=50, l=20, r=20, b=20))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No duplicate values found in any column.")

            elif qres.status_code == 404:
                st.error("Table not found.")
            else:
                st.error("Could not load quality report.")