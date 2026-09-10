import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json

st.set_page_config(
    page_title="DataMind AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_URL = "http://127.0.0.1:8000"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }

    .stApp { background: #f8fafc; }
    .block-container { padding: 1.5rem 2.5rem 2rem; max-width: 1400px; }
    div[data-testid="column"] { padding: 0 0.75rem; }
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Hero ── */
    .hero {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -40%;
        right: -5%;
        width: 350px;
        height: 350px;
        background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title { font-size: 2rem; font-weight: 700; color: #fff; margin: 0 0 0.3rem; letter-spacing: -0.5px; }
    .hero-title span { color: #e0e7ff; }
    .hero-sub { color: rgba(255,255,255,0.8); font-size: 0.95rem; margin: 0; }
    .hero-badges { margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .badge {
        background: rgba(255,255,255,0.2);
        border: 1px solid rgba(255,255,255,0.3);
        color: #fff;
        border-radius: 999px;
        padding: 3px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }

    /* ── Tabs ── */
    div[data-testid="stTabs"] {
        background: #fff;
        border-radius: 12px;
        padding: 4px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stTabs"] button {
        background: transparent;
        color: #64748b;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 0.5rem 1rem;
        border: none;
        transition: all 0.2s;
    }
    div[data-testid="stTabs"] button:hover { color: #6366f1; background: #f5f3ff; }
    div[data-testid="stTabs"] button[aria-selected="true"] { background: #6366f1 !important; color: #fff !important; }
    div[data-testid="stTabs"] [role="tabpanel"] { padding: 1.5rem 0.5rem 0; }
    div[data-testid="stTabs"] [data-baseweb="tab-border"] { margin-top: 4px; }

    /* ── Metrics ── */
    div[data-testid="stMetric"] {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetric"] label { color: #64748b !important; font-size: 0.72rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.05em; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #1e293b !important; font-size: 1.5rem !important; font-weight: 700 !important; }

    /* ── Inputs ── */
    .stTextInput input {
        background: #fff !important;
        border: 1.5px solid #e2e8f0 !important;
        border-radius: 8px !important;
        color: #1e293b !important;
        font-size: 0.9rem !important;
    }
    .stTextInput input:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important; }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s !important;
        box-shadow: 0 2px 8px rgba(99,102,241,0.25) !important;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(99,102,241,0.35) !important; }

    /* ── File uploader ── */
    div[data-testid="stFileUploader"] {
        background: #fff;
        border: 1.5px dashed #cbd5e1;
        border-radius: 10px;
        padding: 0.5rem;
    }
    div[data-testid="stFileUploader"]:hover { border-color: #6366f1; }

    /* ── Expanders ── */
    div[data-testid="stExpander"] {
        background: #fff;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Dataframes ── */
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }

    /* ── Custom components ── */
    .card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        color: #1e293b;
        font-size: 0.95rem;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .insight-box {
        background: #f5f3ff;
        border: 1px solid #ddd6fe;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 0.85rem 1.2rem;
        margin-bottom: 1rem;
        color: #4c1d95;
        font-size: 0.9rem;
    }

    .join-badge {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-left: 4px solid #f59e0b;
        border-radius: 10px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.75rem;
        color: #92400e;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .pill {
        display: inline-block;
        background: #ede9fe;
        border: 1px solid #ddd6fe;
        color: #5b21b6;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 2px 3px;
        font-family: monospace;
    }

    .verdict-good  { background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; color: #065f46; border-radius: 10px; padding: 0.75rem 1rem; font-weight: 600; margin-bottom: 1rem; }
    .verdict-warn  { background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; color: #92400e; border-radius: 10px; padding: 0.75rem 1rem; font-weight: 600; margin-bottom: 1rem; }
    .verdict-bad   { background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 10px; padding: 0.75rem 1rem; font-weight: 600; margin-bottom: 1rem; }

    .section-title {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #94a3b8;
        margin: 1.25rem 0 0.5rem;
    }

    hr { border-color: #f1f5f9 !important; }
    .stSpinner > div { border-top-color: #6366f1 !important; }
    .stCodeBlock { border-radius: 8px !important; border: 1px solid #e2e8f0 !important; }

    /* ── Issue warning boxes ── */
    div[data-testid="stAlert"] {
        border-radius: 8px !important;
        border: 1px solid #fde68a !important;
        border-left: 4px solid #f59e0b !important;
        background: #fffbeb !important;
        padding: 0.6rem 1rem !important;
        margin-bottom: 0.4rem !important;
    }
    div[data-testid="stAlert"] p {
        color: #92400e !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        margin: 0 !important;
    }
    div[data-testid="stAlert"][data-baseweb="notification"] svg {
        color: #f59e0b !important;
    }

    /* ── Success alert ── */
    div[data-testid="stAlert"].st-success {
        border-color: #bbf7d0 !important;
        border-left-color: #10b981 !important;
        background: #f0fdf4 !important;
    }

    /* ── Toggle switch ── */
    div[data-testid="stToggle"] label { color: #475569 !important; font-size: 0.85rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-title">⚡ Data<span>Mind</span> AI</div>
    <p class="hero-sub">Natural language interface for documents and structured data — powered by LLaMA-3 + FAISS + DuckDB</p>
    <div class="hero-badges">
        <span class="badge">🔍 Hybrid RAG</span>
        <span class="badge">📊 NL → SQL</span>
        <span class="badge">🔄 Data Reconciliation</span>
        <span class="badge">🧬 Quality Profiling</span>
        <span class="badge">🚀 Groq LLaMA-3</span>
    </div>
</div>
""", unsafe_allow_html=True)

tab_docs, tab_data, tab_quality, tab_compare, tab_api = st.tabs([
    "📄  Document Q&A",
    "📊  Data Analysis",
    "🔍  Data Quality",
    "🔄  Compare Tables",
    "🌐  API Ingestion",
])

PLOTLY_THEME = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#fafafa",
    font=dict(family="Inter", color="#475569"),
    margin=dict(t=50, l=20, r=20, b=20),
    height=420,
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Document Q&A
# ══════════════════════════════════════════════════════════════════════════════
with tab_docs:
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.markdown('<div class="section-title">Upload Documents</div>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "PDF or TXT", accept_multiple_files=True, type=["txt", "pdf"],
            key="doc_uploader", label_visibility="collapsed",
        )
        if st.button("⬆️  Upload & Index", use_container_width=True):
            if uploaded_files:
                files = [("files", (f.name, f, f.type)) for f in uploaded_files]
                with st.spinner("Chunking and indexing…"):
                    res = requests.post(f"{API_URL}/upload", files=files)
                if res.status_code == 200:
                    d = res.json()
                    st.success(f"✅ Indexed **{d['new_chunks_added']}** chunks · {d['total_chunks']} total")
                else:
                    st.error(res.text)
            else:
                st.warning("Select at least one file.")

        st.markdown('<div class="section-title">Indexed Documents</div>', unsafe_allow_html=True)
        if st.button("↻  Refresh", use_container_width=True, key="refresh_docs"):
            res = requests.get(f"{API_URL}/documents")
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                if docs:
                    for doc in docs:
                        st.markdown(f"<span class='pill'>📄 {doc}</span>", unsafe_allow_html=True)
                else:
                    st.info("No documents uploaded yet.")

    with right:
        st.markdown('<div class="section-title">Ask a Question</div>', unsafe_allow_html=True)
        question = st.text_input("question", placeholder="e.g. What are the key findings?", label_visibility="collapsed")

        if st.button("🔍  Get Answer", use_container_width=True):
            if question.strip():
                with st.spinner("Retrieving context and generating answer…"):
                    res = requests.post(f"{API_URL}/ask", json={"question": question})
                if res.status_code == 200:
                    data = res.json()
                    st.markdown('<div class="section-title">Answer</div>', unsafe_allow_html=True)
                    st.markdown(f"<div class='card'>{data['answer']}</div>", unsafe_allow_html=True)
                    st.markdown('<div class="section-title">Sources</div>', unsafe_allow_html=True)
                    for src in data.get("sources", []):
                        st.markdown(f"<span class='pill'>📄 {src}</span>", unsafe_allow_html=True)
                    with st.expander("🔎  Rewritten query & retrieved chunks"):
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

    with d_left:
        st.markdown('<div class="section-title">Upload Data Files</div>', unsafe_allow_html=True)
        st.caption("CSV and Excel. Each file becomes a queryable table.")
        data_files = st.file_uploader(
            "CSV or Excel", accept_multiple_files=True, type=["csv", "xlsx", "xls"],
            key="data_uploader", label_visibility="collapsed",
        )
        if st.button("⬆️  Upload to Database", use_container_width=True):
            if data_files:
                files = [("files", (f.name, f, f.type)) for f in data_files]
                with st.spinner("Ingesting into DuckDB…"):
                    res = requests.post(f"{API_URL}/upload-data", files=files)
                if res.status_code == 200:
                    for r in res.json().get("results", []):
                        if r["status"] == "success":
                            st.success(f"✅ **{r['file']}** → `{r['rows']}` rows, {len(r['columns'])} cols")
                        elif r["status"] == "skipped":
                            st.warning(f"⚠️ {r['file']}: {r['reason']}")
                        else:
                            st.error(f"❌ {r['file']}: {r['reason']}")
                else:
                    st.error(res.text)
            else:
                st.warning("Select at least one file.")

        st.markdown('<div class="section-title">Available Tables</div>', unsafe_allow_html=True)
        if st.button("↻  Refresh tables", use_container_width=True, key="refresh_tables"):
            res = requests.get(f"{API_URL}/data-tables")
            if res.status_code == 200:
                tables = res.json().get("tables", [])
                if tables:
                    if len(tables) > 1:
                        all_cols = {}
                        for t in tables:
                            for col in t["columns"]:
                                all_cols.setdefault(col, []).append(t["table"])
                        shared = {col: tbls for col, tbls in all_cols.items() if len(tbls) > 1}
                        if shared:
                            st.info("🔗 Joinable: " + " · ".join([f"`{c}`" for c in shared]))
                    for t in tables:
                        with st.expander(f"🗄️ `{t['table']}` — {t['row_count']:,} rows"):
                            st.caption(f"Source: {t['source_file']}")
                            for col in t["columns"]:
                                st.markdown(f"- `{col}`")
                else:
                    st.info("No tables yet.")

    with d_right:
        st.markdown('<div class="section-title">Ask a Data Question</div>', unsafe_allow_html=True)
        st.caption("AI writes SQL, runs it, and builds a chart — including multi-table joins.")

        examples = [
            "Show total sales by department as a bar chart",
            "What are the top 5 products by revenue?",
            "Show monthly trend of orders over time",
            "Which region has the highest average order amount?",
        ]
        selected = st.selectbox("example", [""] + examples, label_visibility="collapsed",
                                format_func=lambda x: "💡 Pick an example…" if x == "" else x)
        data_question = st.text_input("data question", value=selected,
                                      placeholder="e.g. Show total revenue by region as a bar chart",
                                      label_visibility="collapsed")
        chart_override = st.selectbox("Chart type", ["Auto-detect", "bar", "line", "pie", "scatter", "histogram", "table"])

        if st.button("📊  Generate", use_container_width=True):
            if data_question.strip():
                with st.spinner("Writing SQL and building chart…"):
                    res = requests.post(f"{API_URL}/analyze", json={"question": data_question})

                if res.status_code == 200:
                    result = res.json()
                    tables_used = result.get("tables_used", [])
                    if result.get("join_used"):
                        pills = "".join([f"<span class='pill'>{t}</span>" for t in tables_used])
                        st.markdown(f"<div class='join-badge'>🔗 Join across {len(tables_used)} tables: {pills}</div>", unsafe_allow_html=True)
                    elif tables_used:
                        pills = "".join([f"<span class='pill'>{t}</span>" for t in tables_used])
                        st.markdown(f"<div style='margin-bottom:0.5rem;font-size:0.8rem;color:#94a3b8;'>Table: {pills}</div>", unsafe_allow_html=True)

                    if result.get("insight"):
                        st.markdown(f"<div class='insight-box'>💡 {result['insight']}</div>", unsafe_allow_html=True)

                    data_records = result.get("data", [])
                    chart_config = result.get("chart_config", {})
                    chart_type = chart_override if chart_override != "Auto-detect" else result.get("chart_type", "bar")

                    if not data_records:
                        st.info("The query returned no results.")
                    else:
                        df = pd.DataFrame(data_records)
                        numeric_cols = df.select_dtypes(include="number").columns.tolist()
                        all_cols = list(df.columns)
                        listing_kw = ["list", "show me", "give me", "what are", "display", "which", "who", "all"]
                        force_table = chart_type == "table" or not numeric_cols or (any(w in data_question.lower() for w in listing_kw) and len(all_cols) > 2)

                        if force_table:
                            st.markdown(f"**{len(df):,} rows · {len(all_cols)} columns**")
                            st.dataframe(df, use_container_width=True, height=min(400, 38 + len(df) * 35), hide_index=True)
                            if numeric_cols and len(all_cols) >= 2:
                                with st.expander("📊 View as chart"):
                                    cat_cols = [c for c in all_cols if c not in numeric_cols]
                                    fig = px.bar(df, x=cat_cols[0] if cat_cols else all_cols[0], y=numeric_cols[0],
                                                 title=data_question, color=cat_cols[0] if cat_cols else None,
                                                 color_discrete_sequence=px.colors.qualitative.Vivid)
                                    fig.update_layout(**PLOTLY_THEME)
                                    fig.update_layout(showlegend=False)
                                    st.plotly_chart(fig, use_container_width=True)
                        else:
                            x = chart_config.get("x")
                            y = chart_config.get("y")
                            fig = None
                            if chart_type == "bar":
                                fig = px.bar(df, x=x, y=y, title=data_question, color=x,
                                             color_discrete_sequence=px.colors.qualitative.Vivid)
                                fig.update_layout(showlegend=False)
                            elif chart_type == "line":
                                fig = px.line(df, x=x, y=y, title=data_question, markers=True,
                                              color_discrete_sequence=["#6366f1"])
                            elif chart_type == "pie":
                                fig = px.pie(df, names=chart_config.get("names", x),
                                             values=chart_config.get("values", y), title=data_question,
                                             color_discrete_sequence=px.colors.qualitative.Vivid)
                            elif chart_type == "scatter":
                                fig = px.scatter(df, x=x, y=y, title=data_question,
                                                 color=chart_config["categorical_columns"][0] if chart_config.get("categorical_columns") else None)
                            elif chart_type == "histogram":
                                fig = px.histogram(df, x=x, title=data_question,
                                                   color_discrete_sequence=["#6366f1"])
                            if fig:
                                fig.update_layout(**PLOTLY_THEME)
                                st.plotly_chart(fig, use_container_width=True)
                            with st.expander("📋 View as table"):
                                st.dataframe(df, use_container_width=True, hide_index=True)

                        st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), "results.csv", "text/csv")

                    with st.expander("🔧 Generated SQL"):
                        st.code(result.get("sql", ""), language="sql")

                elif res.status_code == 422:
                    st.error(f"❌ {res.json().get('detail', 'Analysis failed.')}")
                else:
                    st.error(res.text)
            else:
                st.warning("Enter a question or pick an example.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Data Quality
# ══════════════════════════════════════════════════════════════════════════════
with tab_quality:
    st.markdown('<div class="section-title">Data Quality Report</div>', unsafe_allow_html=True)
    res = requests.get(f"{API_URL}/data-tables")
    if res.status_code != 200 or not res.json().get("tables"):
        st.info("Upload a CSV or Excel file in the Data Analysis tab first.")
    else:
        tables = res.json()["tables"]
        selected_table = st.selectbox("Select table", [t["table"] for t in tables])

        if st.button("🔍  Run Quality Check", use_container_width=True):
            qres = requests.get(f"{API_URL}/quality/{selected_table}")
            if qres.status_code == 200:
                q = qres.json()
                score = q.get("health_score", 0)
                score_emoji = "✅" if score >= 80 else ("⚠️" if score >= 50 else "❌")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Health Score", f"{score_emoji} {score}/100")
                c2.metric("Total Rows", f"{q['row_count']:,}")
                c3.metric("Duplicate Rows", f"{q['duplicate_rows']:,}",
                          delta=f"-{q['duplicate_rows']}" if q['duplicate_rows'] > 0 else None,
                          delta_color="inverse")
                c4.metric("Columns", len(q.get("columns", {})))

                issues = q.get("issues", [])
                if issues:
                    st.markdown('<div class="section-title">Issues Found</div>', unsafe_allow_html=True)
                    for issue in issues:
                        st.warning(f"⚠️ {issue}")
                else:
                    st.success("✅ No issues detected — data looks clean!")

                st.markdown('<div class="section-title">Column Profile</div>', unsafe_allow_html=True)
                col_data = []
                for col_name, stats in q.get("columns", {}).items():
                    top_dupes = stats.get("top_duplicate_values", {})
                    dupe_preview = ", ".join([f"{k} (×{v})" for k, v in list(top_dupes.items())[:3]]) if top_dupes else "—"
                    col_data.append({
                        "Column": col_name,
                        "Nulls": f"{stats['null_count']} ({stats['null_pct']}%)",
                        "Unique": stats["unique_count"],
                        "Duplicates": stats["duplicate_value_count"],
                        "Top Duplicates": dupe_preview,
                        "Issues": ", ".join(stats.get("issues", [])) or "—",
                    })
                st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

                st.markdown('<div class="section-title">Duplicate Value Drilldown</div>', unsafe_allow_html=True)
                cols_with_dupes = {k: v["top_duplicate_values"] for k, v in q.get("columns", {}).items() if v.get("top_duplicate_values")}
                if cols_with_dupes:
                    selected_col = st.selectbox("Column to inspect", list(cols_with_dupes.keys()))
                    dupe_df = pd.DataFrame(list(cols_with_dupes[selected_col].items()), columns=["Value", "Count"])
                    fig = px.bar(dupe_df, x="Value", y="Count", title=f"Duplicate values — {selected_col}",
                                 color="Value", color_discrete_sequence=px.colors.qualitative.Vivid)
                    fig.update_layout(**PLOTLY_THEME)
                    fig.update_layout(showlegend=False, height=320)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No duplicate values found.")
            elif qres.status_code == 404:
                st.error("Table not found.")
            else:
                st.error("Could not load quality report.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Compare Tables
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown('<div class="section-title">Table Reconciliation</div>', unsafe_allow_html=True)
    st.caption("Compare two tables — row counts, column overlap, value match rates, and row-level diffs.")

    res = requests.get(f"{API_URL}/data-tables")
    if res.status_code != 200 or not res.json().get("tables"):
        st.info("Upload at least two CSV or Excel files in the Data Analysis tab first.")
    else:
        tables = [t["table"] for t in res.json()["tables"]]
        if len(tables) < 2:
            st.warning("Need at least 2 tables to compare.")
        else:
            c1, c2 = st.columns(2)
            table_a = c1.selectbox("Table A", tables, index=0)
            table_b = c2.selectbox("Table B", tables, index=min(1, len(tables)-1))

            all_tables = {t["table"]: t["columns"] for t in res.json().get("tables", [])}
            shared_cols = sorted(set(all_tables.get(table_a, [])) & set(all_tables.get(table_b, [])))
            key_column = st.selectbox("Key column (optional)", ["None"] + shared_cols)
            key_column = None if key_column == "None" else key_column

            if st.button("🔄  Run Comparison", use_container_width=True):
                if table_a == table_b:
                    st.error("Select two different tables.")
                else:
                    with st.spinner("Comparing tables…"):
                        cres = requests.post(f"{API_URL}/compare", json={
                            "table_a": table_a, "table_b": table_b, "key_column": key_column
                        })

                    if cres.status_code == 200:
                        r = cres.json()
                        overall = r.get("overall_match_pct", 0)
                        verdict = r.get("verdict", "")
                        css = "verdict-good" if overall == 100 else ("verdict-warn" if overall >= 90 else "verdict-bad")
                        st.markdown(f"<div class='{css}'>{verdict} — {overall}% overall match</div>", unsafe_allow_html=True)

                        st.markdown('<div class="section-title">Row Counts</div>', unsafe_allow_html=True)
                        rc = r["row_counts"]
                        m1, m2, m3 = st.columns(3)
                        m1.metric(f"Rows in {table_a}", f"{rc['table_a']:,}")
                        m2.metric(f"Rows in {table_b}", f"{rc['table_b']:,}")
                        m3.metric("Difference", rc["difference"], delta_color="off" if rc["difference"] == 0 else "inverse")

                        st.markdown('<div class="section-title">Column Overlap</div>', unsafe_allow_html=True)
                        co = r["column_overlap"]
                        mc1, mc2, mc3 = st.columns(3)
                        mc1.metric("Shared Columns", co["shared_count"])
                        mc2.metric(f"Only in {table_a}", len(co["only_in_a"]))
                        mc3.metric(f"Only in {table_b}", len(co["only_in_b"]))
                        if co["only_in_a"]:
                            st.info(f"Only in **{table_a}**: `{'`, `'.join(co['only_in_a'])}`")
                        if co["only_in_b"]:
                            st.info(f"Only in **{table_b}**: `{'`, `'.join(co['only_in_b'])}`")

                        st.markdown('<div class="section-title">Row-Level Overlap</div>', unsafe_allow_html=True)
                        rl = r.get("row_level", {})
                        rl1, rl2, rl3, rl4 = st.columns(4)
                        rl1.metric("Rows in Both", f"{rl.get('rows_in_both', 0):,}")
                        rl2.metric(f"Only in {table_a}", f"{rl.get('rows_only_in_a', 0):,}")
                        rl3.metric(f"Only in {table_b}", f"{rl.get('rows_only_in_b', 0):,}")
                        rl4.metric("Exact Match %", f"{rl.get('exact_match_pct', 0)}%")

                        dup = r.get("duplicates", {})
                        if dup:
                            st.markdown('<div class="section-title">Duplicate Rows</div>', unsafe_allow_html=True)
                            d1, d2, d3 = st.columns(3)
                            d1.metric(f"Dupes in {table_a}", dup.get("within_a", 0))
                            d2.metric(f"Dupes in {table_b}", dup.get("within_b", 0))
                            d3.metric("Identical across both", dup.get("identical_rows_across_tables", 0))

                        vc = r.get("value_comparison", {})
                        if vc:
                            st.markdown('<div class="section-title">Column-Level Value Comparison</div>', unsafe_allow_html=True)
                            col_rows = [{"Column": col, "Status": s["status"], "Match %": f"{s['match_pct']}%",
                                         "Matches": s["match_count"], "Mismatches": s["mismatch_count"],
                                         "Unique in A": s["unique_values_a"], "Unique in B": s["unique_values_b"]}
                                        for col, s in vc.items()]
                            st.dataframe(pd.DataFrame(col_rows), use_container_width=True, hide_index=True)

                            chart_df = pd.DataFrame([{"Column": col, "Match %": s["match_pct"]} for col, s in vc.items()])
                            fig = px.bar(chart_df, x="Column", y="Match %", title="Value match % per column",
                                         color="Match %", color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                                         range_color=[0, 100])
                            fig.update_layout(**PLOTLY_THEME)
                            fig.update_layout(height=320)
                            st.plotly_chart(fig, use_container_width=True)

                            with st.expander("🔍 Value differences per column"):
                                for col, stats in vc.items():
                                    if stats["values_only_in_a"] or stats["values_only_in_b"]:
                                        st.markdown(f"**`{col}`**")
                                        d1c, d2c = st.columns(2)
                                        if stats["values_only_in_a"]:
                                            d1c.markdown(f"Only in **{table_a}**:")
                                            for v in stats["values_only_in_a"][:10]:
                                                d1c.markdown(f"- `{v}`")
                                        if stats["values_only_in_b"]:
                                            d2c.markdown(f"Only in **{table_b}**:")
                                            for v in stats["values_only_in_b"][:10]:
                                                d2c.markdown(f"- `{v}`")
                                        st.markdown("---")

                        if "key_analysis" in r:
                            st.markdown(f'<div class="section-title">Key-Based Diff — {r["key_analysis"]["key_column"]}</div>', unsafe_allow_html=True)
                            ka = r["key_analysis"]
                            k1, k2, k3, k4 = st.columns(4)
                            k1.metric("Common Keys", f"{ka['common_keys']:,}")
                            k2.metric(f"Only in {table_a}", len(ka["keys_only_in_a"]))
                            k3.metric(f"Only in {table_b}", len(ka["keys_only_in_b"]))
                            k4.metric("Rows with Diffs", ka["rows_with_differences"])

                            if ka["keys_only_in_a"]:
                                st.warning(f"Keys only in **{table_a}**: `{', '.join(ka['keys_only_in_a'][:10])}`")
                            if ka["keys_only_in_b"]:
                                st.warning(f"Keys only in **{table_b}**: `{', '.join(ka['keys_only_in_b'][:10])}`")

                            if ka["mismatch_details"]:
                                with st.expander(f"🔍 {ka['rows_with_differences']} rows differ"):
                                    for m in ka["mismatch_details"][:20]:
                                        st.markdown(f"**Key `{m['key']}`** — changed in: `{'`, `'.join(m['differing_columns'])}`")
                                        diff_rows = [{"Column": col, f"{table_a}": m["values_a"][col], f"{table_b}": m["values_b"][col]}
                                                     for col in m["differing_columns"]]
                                        st.dataframe(pd.DataFrame(diff_rows), use_container_width=True, hide_index=True)
                                        st.markdown("---")
                            else:
                                st.success("✅ No row-level differences on common keys.")

                        st.download_button("⬇️ Download report JSON", json.dumps(r, indent=2),
                                           f"compare_{table_a}_vs_{table_b}.json", "application/json")

                    elif cres.status_code == 422:
                        st.error(cres.json().get("detail", "Comparison failed."))
                    else:
                        st.error(cres.text)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — API Ingestion
# ══════════════════════════════════════════════════════════════════════════════
with tab_api:
    st.markdown('<div class="section-title">API Ingestion Pipeline</div>', unsafe_allow_html=True)
    st.caption("Fetch data from any REST API — auto-flattens JSON, saves to DuckDB, runs quality check, and exports CSV.")

    a_left, a_right = st.columns([1, 1], gap="large")

    with a_left:
        st.markdown('<div class="section-title">API Configuration</div>', unsafe_allow_html=True)

        api_url = st.text_input("API URL", placeholder="https://api.example.com/v1/data")
        method = st.selectbox("HTTP Method", ["GET", "POST"])

        st.markdown('<div class="section-title">Authentication</div>', unsafe_allow_html=True)
        auth_type = st.selectbox("Auth Type", ["none", "bearer", "api_key", "basic"],
                                  format_func=lambda x: {
                                      "none": "No Auth",
                                      "bearer": "Bearer Token",
                                      "api_key": "API Key Header",
                                      "basic": "Basic Auth (user:password)"
                                  }[x])

        auth_token = None
        api_key_header = None
        api_key_value = None

        if auth_type == "bearer":
            auth_token = st.text_input("Bearer Token", type="password", placeholder="eyJ...")
        elif auth_type == "api_key":
            api_key_header = st.text_input("Header Name", placeholder="X-API-Key")
            api_key_value = st.text_input("API Key Value", type="password")
        elif auth_type == "basic":
            auth_token = st.text_input("Credentials", type="password", placeholder="username:password")

        st.markdown('<div class="section-title">Pagination</div>', unsafe_allow_html=True)
        paginate = st.toggle("Enable pagination")
        max_pages = 5
        page_param = "page"
        if paginate:
            max_pages = st.slider("Max pages to fetch", 1, 20, 5)
            page_param = st.text_input("Page parameter name", value="page", placeholder="page / offset / cursor")

        st.markdown('<div class="section-title">Table Name (optional)</div>', unsafe_allow_html=True)
        table_name = st.text_input("Save as table", placeholder="auto-detected from URL")

        if method == "POST":
            st.markdown('<div class="section-title">Request Body (JSON)</div>', unsafe_allow_html=True)
            body_str = st.text_area("Body", placeholder='{"key": "value"}', height=100)
        else:
            body_str = None

    with a_right:
        st.markdown('<div class="section-title">Quick Examples</div>', unsafe_allow_html=True)
        examples = {
            "JSONPlaceholder — Posts": "https://jsonplaceholder.typicode.com/posts",
            "JSONPlaceholder — Users": "https://jsonplaceholder.typicode.com/users",
            "Open Meteo — Weather": "https://api.open-meteo.com/v1/forecast?latitude=39.1&longitude=-84.5&hourly=temperature_2m&forecast_days=3",
            "REST Countries": "https://restcountries.com/v3.1/all?fields=name,population,region,area",
            "CoinGecko — Crypto": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=20&page=1",
        }
        selected_example = st.selectbox("Pick an example to auto-fill URL",
                                         [""] + list(examples.keys()),
                                         format_func=lambda x: "Choose an example…" if x == "" else x)
        if selected_example:
            st.info(f"Copy this URL into the API URL field:`{examples[selected_example]}`")

        st.markdown('<div class="section-title">Result Preview</div>', unsafe_allow_html=True)

        if st.button("🚀  Fetch & Ingest", use_container_width=True):
            if not api_url.strip():
                st.warning("Enter an API URL first.")
            else:
                body = None
                if body_str:
                    try:
                        body = json.loads(body_str)
                    except:
                        st.error("Request body is not valid JSON.")
                        st.stop()

                payload = {
                    "url": api_url.strip(),
                    "method": method,
                    "auth_type": auth_type,
                    "auth_token": auth_token,
                    "api_key_header": api_key_header,
                    "api_key_value": api_key_value,
                    "body": body,
                    "paginate": paginate,
                    "max_pages": max_pages,
                    "page_param": page_param,
                    "table_name": table_name.strip() if table_name.strip() else None,
                }

                with st.spinner("Fetching data from API…"):
                    res = requests.post(f"{API_URL}/fetch-api", json=payload)

                if res.status_code == 200:
                    r = res.json()

                    # ── Summary metrics ───────────────────────────────────
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Records Fetched", f"{r['total_records']:,}")
                    m2.metric("Pages", r["pages_fetched"])
                    m3.metric("Columns", len(r["columns"]))
                    q = r.get("quality", {})
                    score = q.get("health_score", 0) if q else 0
                    score_emoji = "✅" if score >= 80 else ("⚠️" if score >= 50 else "❌")
                    m4.metric("Quality Score", f"{score_emoji} {score}/100")

                    if r.get("warnings"):
                        for w in r["warnings"]:
                            st.warning(f"⚠️ {w}")

                    st.success(f"✅ Saved as table `{r['table_name']}` — ready to query in Data Analysis tab")

                    # ── Column list ───────────────────────────────────────
                    st.markdown('<div class="section-title">Columns Detected</div>', unsafe_allow_html=True)
                    cols_str = "  ".join([f"`{c}`" for c in r["columns"]])
                    st.markdown(cols_str)

                    # ── Sample data ───────────────────────────────────────
                    st.markdown('<div class="section-title">Sample Data (first 5 rows)</div>', unsafe_allow_html=True)
                    sample_df = pd.DataFrame(r["sample"])
                    st.dataframe(sample_df, use_container_width=True, hide_index=True)

                    # ── Quality report ────────────────────────────────────
                    if q:
                        st.markdown('<div class="section-title">Automatic Quality Check</div>', unsafe_allow_html=True)
                        issues = q.get("issues", [])
                        if issues:
                            for issue in issues:
                                st.warning(f"⚠️ {issue}")
                        else:
                            st.success("✅ No quality issues detected")

                        col_data = []
                        for col_name, stats in q.get("columns", {}).items():
                            col_data.append({
                                "Column": col_name,
                                "Nulls": f"{stats['null_count']} ({stats['null_pct']}%)",
                                "Unique": stats["unique_count"],
                                "Duplicates": stats["duplicate_value_count"],
                                "Issues": ", ".join(stats.get("issues", [])) or "—",
                            })
                        if col_data:
                            st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

                    # ── Download ──────────────────────────────────────────
                    st.download_button(
                        "⬇️ Download as CSV",
                        data=r["csv"],
                        file_name=f"{r['table_name']}.csv",
                        mime="text/csv",
                    )

                    st.info(f"💡 Go to **📊 Data Analysis** tab and ask questions about `{r['table_name']}`")

                elif res.status_code == 422:
                    st.error(f"❌ {res.json().get('detail', 'Fetch failed.')}")
                else:
                    st.error(res.text)