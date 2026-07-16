import faiss
import numpy as np
import pandas as pd
from groq import Groq

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter

from pypdf import PdfReader
from typing import List

import os
import json
import io

from rank_bm25 import BM25Okapi

# New imports for data analysis
from database import ingest_file_to_db, list_tables, get_schema_prompt, get_quality_report
from chart import answer_data_question

from dotenv import load_dotenv
load_dotenv()

bm25 = None
tokenized_corpus = []

# Initialize FastAPI
app = FastAPI()

# Initialize Groq client
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

# Load embedding model (local)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

INDEX_PATH = "faiss_index.bin"
CHUNKS_PATH = "chunks.json"

# Global storage (in-memory)
vector_index = None
chunk_store = {}

# Request models
class QuestionRequest(BaseModel):
    question: str

class AnalyzeRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"message": "Local AI RAG + Data Analysis app running with Groq 🚀"}

@app.on_event("startup")
def startup_event():
    load_data()


def load_data():
    global vector_index, chunk_store

    if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
        vector_index = faiss.read_index(INDEX_PATH)

        with open(CHUNKS_PATH, "r") as f:
            chunk_store = json.load(f)

        chunk_store = {int(k): v for k, v in chunk_store.items()}
        print("✅ Loaded existing index and chunks")
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
        print("⚠️ No data for BM25 yet")
        bm25 = None
        return

    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    print("✅ BM25 index built")


# =========================
# 📥 UPLOAD DOCUMENTS (existing)
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

        embeddings = embedding_model.encode(chunks)

        if vector_index is None:
            dimension = embeddings.shape[1]
            vector_index = faiss.IndexFlatL2(dimension)

        start_idx = len(chunk_store)
        vector_index.add(np.array(embeddings).astype("float32"))

        for i, chunk in enumerate(chunks):
            chunk_store[start_idx + i] = {
                "text": chunk,
                "embedding": embeddings[i].tolist(),
                "source": file.filename,
                "chunk_id": start_idx + i
            }

        faiss.write_index(vector_index, INDEX_PATH)

        with open(CHUNKS_PATH, "w") as f:
            json.dump(chunk_store, f)

        print("💾 Data saved to disk")
        build_bm25()
        total_new_chunks += len(chunks)

    return {
        "message": "Files uploaded successfully",
        "new_chunks_added": total_new_chunks,
        "total_chunks": len(chunk_store)
    }


# =========================
# 📊 UPLOAD DATA FILES (new)
# =========================

@app.post("/upload-data")
async def upload_data_files(files: List[UploadFile] = File(...)):
    """
    Upload CSV or Excel files to be stored in SQLite for data analysis / chart generation.
    """
    results = []

    for file in files:
        filename = file.filename
        content = await file.read()

        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
            elif filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(content))
            else:
                results.append({"file": filename, "status": "skipped", "reason": "Unsupported format (use CSV or Excel)"})
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

    return {"results": results}


@app.get("/data-tables")
def get_data_tables():
    """List all ingested data tables with their schema."""
    tables = list_tables()
    return {"tables": tables}


# =========================
# 🔍 DATA QUALITY (new)
# =========================

@app.get("/quality/{table_name}")
def get_table_quality(table_name: str):
    """Return the data quality profile for a specific table."""
    report = get_quality_report(table_name)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return report


# =========================
# 📈 ANALYZE / CHART (new)
# =========================

@app.post("/analyze")
def analyze_question(request: AnalyzeRequest):
    """
    Answer a data question with SQL + chart data.
    The response contains everything needed to render a Plotly chart.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = answer_data_question(question)

    if not result["success"]:
        raise HTTPException(status_code=422, detail=result.get("error", "Analysis failed"))

    return result


# =========================
# ❓ ASK ENDPOINT (existing)
# =========================

@app.post("/ask")
def ask_question(request: QuestionRequest):
    global vector_index, chunk_store

    if vector_index is None or not chunk_store:
        raise HTTPException(status_code=400, detail="Upload a file first")

    original_question = request.question.strip()

    if not original_question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    rewritten_question = rewrite_query(original_question)

    print("Original:", original_question)
    print("Rewritten:", rewritten_question)

    question_embedding = embedding_model.encode([rewritten_question])[0]

    distances, indices = vector_index.search(
        np.array([question_embedding]).astype("float32"),
        k=8
    )

    semantic_candidates = [chunk_store[i] for i in indices[0] if i in chunk_store]

    if bm25 is not None:
        query_tokens = rewritten_question.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:5]
        keyword_candidates = [chunk_store[i] for i in top_bm25_indices]
    else:
        keyword_candidates = []

    combined = {}
    for c in semantic_candidates + keyword_candidates:
        combined[c["chunk_id"]] = c

    candidates = list(combined.values())

    scored = []
    for c in candidates:
        if "embedding" not in c:
            continue
        chunk_embedding = np.array(c["embedding"])
        score = cosine_similarity(question_embedding, chunk_embedding)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [item[1] for item in scored[:3]]

    retrieved_chunks = [c["text"] for c in top_chunks]
    sources = [c["source"] for c in top_chunks]

    if not retrieved_chunks:
        raise HTTPException(status_code=404, detail="No relevant context found")

    context = ""
    for chunk in top_chunks:
        context += f"[Source: {chunk['source']}]\n{chunk['text']}\n\n"

    prompt = f"""
You are a precise assistant.

Use only the context below to answer the question.
If the answer is not in the context, say: "I don't know based on the provided document."
Do not make up information.
Keep the answer clear and concise.

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
        "sources": sources,
        "context_used": retrieved_chunks
    }


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def rewrite_query(question: str) -> str:
    prompt = f"""
Rewrite the user question to improve retrieval from documents.
Make it specific, clear, and include important keywords.
Do NOT answer the question.

Original Question:
{question}
"""

    return chat(prompt)