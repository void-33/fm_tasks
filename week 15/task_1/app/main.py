from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
import os

app = FastAPI(
    title="AI Assistant API",
    description="A robust AI assistant utilizing Gemini API, Ollama, and RAG architectures.",
    version="1.0.0"
)

# Ensure static dir exists
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
