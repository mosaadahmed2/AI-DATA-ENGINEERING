import streamlit as st
import requests

st.set_page_config(page_title="AI Document Assistant", page_icon="📄", layout="wide")

API_URL = "http://127.0.0.1:8000"

st.title("📄 AI Document Assistant")
st.markdown(
    "Upload PDF or TXT files, then ask questions across your documents using a local RAG pipeline."
)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files",
        accept_multiple_files=True,
        type=["txt", "pdf"]
    )

    if st.button("Upload Files"):
        if uploaded_files:
            files = [("files", (f.name, f, f.type)) for f in uploaded_files]
            with st.spinner("Uploading and indexing files..."):
                res = requests.post(f"{API_URL}/upload", files=files)

            if res.status_code == 200:
                st.success("Files uploaded successfully")
                st.json(res.json())
            else:
                st.error(res.text)
        else:
            st.warning("Please select at least one file.")

    st.subheader("Indexed Documents")
    if st.button("Refresh Document List"):
        res = requests.get(f"{API_URL}/documents")
        if res.status_code == 200:
            docs = res.json().get("documents", [])
            if docs:
                for doc in docs:
                    st.write(f"- {doc}")
            else:
                st.info("No documents uploaded yet.")
        else:
            st.error("Could not fetch documents.")

with col2:
    st.subheader("Ask a Question")
    question = st.text_input("Enter your question")

    if st.button("Get Answer"):
        if question.strip():
            with st.spinner("Thinking..."):
                res = requests.post(
                    f"{API_URL}/ask",
                    json={"question": question}
                )

            if res.status_code == 200:
                data = res.json()

                st.subheader("Answer")
                st.write(data["answer"])

                st.subheader("Rewritten Query")
                st.code(data.get("rewritten_question", ""), language="text")

                st.subheader("Sources")
                for src in data.get("sources", []):
                    st.write(f"- {src}")

                with st.expander("Retrieved Context"):
                    for i, chunk in enumerate(data.get("context_used", []), 1):
                        st.markdown(f"**Chunk {i}**")
                        st.write(chunk)
                        st.markdown("---")
            else:
                st.error(res.text)
        else:
            st.warning("Please enter a question.")