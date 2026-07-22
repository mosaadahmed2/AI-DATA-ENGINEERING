import faiss
import numpy as np
import pandas as pd
import math
import json as _json
from groq import Groq

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter

from pypdf import PdfReader
from typing import List

import os
import io

from rank_bm25 import BM25Okapi

from database import ingest_file_to_db, list_tables, get_schema_prompt, get_quality_report
from chart import answer_data_question


# ── Global NaN/Inf sanitizer ──────────────────────────────────────────────────
def _sanitize(obj):
    """Recursively replace NaN/Inf with None so json.dumps never raises."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj

def safe_json_response(data):
    return JSONResponse(content=_sanitize(data))


# ── App setup ─────────────────────────────────────────────────────────────────
bm25 = None
tokenized_corpus = []

app = FastAPI()

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

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

INDEX_PATH = "faiss_index.bin"
CHUNKS_PATH = "chunks.json"

FAISS_NLIST  = 50
FAISS_NPROBE = 10
DIMENSION    = 384

vector_index = None
chunk_store  = {}

class QuestionRequest(BaseModel):
    question: str

class AnalyzeRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"message": "AI Data Assistant running with Groq + DuckDB + FAISS IVF 🚀"}


@app.on_event("startup")
def startup_event():
    load_data()


def _build_ivf_index(embeddings_matrix: np.ndarray) -> faiss.Index:
    n = embeddings_matrix.shape[0]
    if n < FAISS_NLIST:
        idx = faiss.IndexFlatL2(DIMENSION)
        idx.add(embeddings_matrix)
        return idx
    quantizer = faiss.IndexFlatL2(DIMENSION)
    idx = faiss.IndexIVFFlat(quantizer, DIMENSION, FAISS_NLIST)
    idx.train(embeddings_matrix)
    idx.add(embeddings_matrix)
    idx.nprobe = FAISS_NPROBE
    return idx


def load_data():
    global vector_index, chunk_store
    if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
        vector_index = faiss.read_index(INDEX_PATH)
        if hasattr(vector_index, 'nprobe'):
            vector_index.nprobe = FAISS_NPROBE
        with open(CHUNKS_PATH, "r") as f:
            chunk_store = {int(k): v for k, v in _json.load(f).items()}
        print(f"✅ Loaded {len(chunk_store)} chunks")
    else:
        print("⚠️ No existing data found")
    build_bm25()


@app.get("/documents")
def list_documents():
    sources = list(set([v["source"] for v in chunk_store.values()]))
    return {"documents": sources}


def build_bm25():
    global bm25, tokenized_corpus
    corpus = [v["text"] for v in chunk_store.values()]
    if not corpus:
        bm25 = None
        return
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    print(f"✅ BM25 built ({len(corpus)} docs)")


# =========================
# 📥 UPLOAD DOCUMENTS
# =========================

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    global vector_index, chunk_store
    total_new_chunks = 0

    for file in files:
        text = ""
        if file.filename.endswith(".pdf"):
            reader = PdfReader(file.file)
            for page in reader.pages:
                text += page.extract_text() or ""
        else:
            content = await file.read()
            text = content.decode("utf-8", errors="ignore")

        if not text.strip():
            continue

        text = " ".join(text.split())
        splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
        chunks = splitter.split_text(text)
        if not chunks:
            continue

        embeddings = embedding_model.encode(chunks, batch_size=32, show_progress_bar=False)
        embeddings_f32 = np.array(embeddings).astype("float32")
        start_idx = len(chunk_store)

        for i, chunk in enumerate(chunks):
            chunk_store[start_idx + i] = {
                "text": chunk,
                "embedding": embeddings[i].tolist(),
                "source": file.filename,
                "chunk_id": start_idx + i,
            }

        all_embeddings = np.array(
            [chunk_store[k]["embedding"] for k in sorted(chunk_store.keys())]
        ).astype("float32")

        vector_index = _build_ivf_index(all_embeddings)
        faiss.write_index(vector_index, INDEX_PATH)

        with open(CHUNKS_PATH, "w") as f:
            _json.dump(chunk_store, f)

        if len(chunk_store) % 10 == 0 or total_new_chunks == 0:
            build_bm25()

        total_new_chunks += len(chunks)

    build_bm25()
    return {
        "message": "Files uploaded successfully",
        "new_chunks_added": total_new_chunks,
        "total_chunks": len(chunk_store),
    }


# =========================
# 📊 UPLOAD DATA FILES
# =========================

CHUNK_SIZE = 50_000

@app.post("/upload-data")
def upload_data_files(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        filename = file.filename
        content = file.file.read()
        try:
            if filename.endswith(".csv"):
                df = pd.concat(
                    pd.read_csv(io.BytesIO(content), chunksize=CHUNK_SIZE, low_memory=False),
                    ignore_index=True,
                )
            elif filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(content))
            else:
                results.append({"file": filename, "status": "skipped", "reason": "Unsupported format"})
                continue

            if df.empty:
                results.append({"file": filename, "status": "skipped", "reason": "File is empty"})
                continue

            info = ingest_file_to_db(filename, df)
            quality = info.get("quality", {})
            results.append({
                "file": filename,
                "status": "success",
                "table": info.get("source_file"),
                "rows": info["row_count"],
                "columns": info["columns"],
                "health_score": quality.get("health_score"),
                "duplicate_rows": quality.get("duplicate_row_count", 0),
                "issues": quality.get("issues", []),
            })
        except Exception as e:
            results.append({"file": filename, "status": "error", "reason": str(e)})

    return safe_json_response({"results": results})


@app.get("/data-tables")
def get_data_tables():
    return safe_json_response({"tables": list_tables()})


# =========================
# 🔍 DATA QUALITY
# =========================

@app.get("/quality/{table_name}")
def get_table_quality(table_name: str):
    report = get_quality_report(table_name)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return safe_json_response(report)


# =========================
# 📈 ANALYZE
# =========================

@app.post("/analyze")
def analyze_question(request: AnalyzeRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = answer_data_question(question)
    if not result["success"]:
        raise HTTPException(status_code=422, detail=result.get("error", "Analysis failed"))
    return safe_json_response(result)


# =========================
# ❓ ASK
# =========================

@app.post("/ask")
def ask_question(request: QuestionRequest):
    global vector_index, chunk_store

    if vector_index is None or not chunk_store:
        raise HTTPException(status_code=400, detail="Upload a document first")

    original_question = request.question.strip()
    if not original_question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    rewritten_question = rewrite_query(original_question)
    question_embedding = embedding_model.encode([rewritten_question])[0]

    if hasattr(vector_index, 'nprobe'):
        vector_index.nprobe = FAISS_NPROBE

    distances, indices = vector_index.search(
        np.array([question_embedding]).astype("float32"),
        k=min(8, len(chunk_store)),
    )

    semantic_candidates = [chunk_store[i] for i in indices[0] if i in chunk_store]

    if bm25 is not None:
        query_tokens = rewritten_question.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:5]
        keyword_candidates = [chunk_store[i] for i in top_bm25_indices if i in chunk_store]
    else:
        keyword_candidates = []

    combined = {}
    for c in semantic_candidates + keyword_candidates:
        combined[c["chunk_id"]] = c

    scored = [
        (cosine_similarity(question_embedding, np.array(c["embedding"])), c)
        for c in combined.values() if "embedding" in c
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [item[1] for item in scored[:3]]

    if not top_chunks:
        raise HTTPException(status_code=404, detail="No relevant context found")

    context = "".join(f"[Source: {c['source']}]\n{c['text']}\n\n" for c in top_chunks)

    prompt = f"""You are a precise assistant.
Use only the context below to answer the question.
If the answer is not in the context, say: "I don't know based on the provided document."
Do not make up information. Keep the answer clear and concise.

Context:
{context}

Question:
{original_question}
"""
    answer = chat(prompt)

    return {
        "question": original_question,
        "rewritten_question": rewritten_question,
        "answer": answer,
        "sources": [c["source"] for c in top_chunks],
        "context_used": [c["text"] for c in top_chunks],
    }


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def rewrite_query(question: str) -> str:
    return chat(f"""Rewrite the user question to improve retrieval from documents.
Make it specific, clear, and include important keywords.
Do NOT answer the question.

Original Question:
{question}
""")