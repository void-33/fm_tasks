from fastapi import APIRouter, File, UploadFile, HTTPException
import tempfile
import os
import PyPDF2

from app.schemas.models import ChatRequest, ChatResponse, IngestRequest
from app.services.rag import rag_service
from app.services.llm import get_gemini_response, get_ollama_response

router = APIRouter()

@router.post("/ingest/text")
async def ingest_text(request: IngestRequest):
    """Ingest raw text into the vector database."""
    try:
        chunks = rag_service.ingest_text(request.text)
        return {"status": "success", "chunks_processed": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    """Upload a file (PDF or TXT) and ingest its contents."""
    try:
        content = ""
        if file.filename.endswith(".pdf"):
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
                
            with open(tmp_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"
            os.unlink(tmp_path)
        else:
            bytes_content = await file.read()
            content = bytes_content.decode("utf-8")
            
        chunks = rag_service.ingest_text(content, source_name=file.filename)
        return {"status": "success", "filename": file.filename, "chunks_processed": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the assistant."""
    context = ""
    sources = []
    
    if request.use_rag:
        try:
            context, sources = rag_service.retrieve_context(request.message)
        except Exception as e:
            print(f"RAG Warning: {e}")
            
    try:
        if request.model_type.lower() == "ollama":
            reply, _ = get_ollama_response(request.message, context, request.temperature)
            structured_data = None
        else:
            reply, structured_data = get_gemini_response(
                request.message, 
                context, 
                request.temperature, 
                request.structured_output
            )
            
        return ChatResponse(
            reply=reply if reply else "No response generated.",
            sources=sources if request.use_rag else None,
            structured_data=structured_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
