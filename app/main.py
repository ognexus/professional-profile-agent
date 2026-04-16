"""
main.py — FastAPI application (stub for v1; Streamlit is the primary UI).

This exists so the project has an API layer ready to productise if needed.
Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI

app = FastAPI(
    title="Professional Profile Agent",
    description="AI-powered candidate assessment and CV curation.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}
