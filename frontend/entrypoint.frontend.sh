#!/bin/bash
# Use API_URL env var if set, otherwise default to localhost
export API_URL=${API_URL:-http://127.0.0.1:8000}
exec python -m streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false