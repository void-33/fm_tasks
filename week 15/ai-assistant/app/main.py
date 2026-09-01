"""FastAPI main application for the AI Assistant."""

import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import llm_client
from app.rag.pipeline import rag
from app.tools.registry import AVAILABLE_TOOLS

app = FastAPI(
    title="AI Assistant API",
    description="A robust AI assistant utilizing Gemini API and RAG architecture.",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Data Models ---

class ChatMessage(BaseModel):
    role: str = Field(description="Role of the sender (user, model, system)")
    content: str = Field(description="Content of the message")

class ChatRequest(BaseModel):
    query: str = Field(description="The user's input/question")
    use_rag: bool = Field(default=False, description="Whether to include retrieved documents in context")
    use_tools: bool = Field(default=False, description="Whether to allow the assistant to use external tools")
    system_prompt: Optional[str] = Field(default=None, description="Custom system instruction for this request")

class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = None
    tools_used: Optional[List[str]] = None

class DataIngestResponse(BaseModel):
    status: str
    details: str
    chunks_created: int

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Assistant API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "model": settings.GEMINI_MODEL}

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Chat with the AI Assistant. Connects to Gemini API and optionally uses RAG or Tools.
    """
    try:
        # 1. RAG Processing
        context = ""
        sources = []
        if request.use_rag:
            retrieved_docs = rag.search(request.query)
            if retrieved_docs:
                sources = retrieved_docs
                context_parts = [
                    f"Document {i+1} (Source: {doc['metadata'].get('source', 'Unknown')}):\n{doc['text']}"
                    for i, doc in enumerate(retrieved_docs)
                ]
                context = "\n\n".join(context_parts)

        # Build the system prompt
        system_prompt = request.system_prompt or "You are a helpful AI assistant."
        if context:
            system_prompt += f"\n\nPlease use the following retrieved information to answer the user's question:\n\n<context>\n{context}\n</context>"

        # 2. Tool Binding & Chat Session
        tools = AVAILABLE_TOOLS if request.use_tools else []

        # Create a new chat session for this request
        chat = llm_client.get_chat_session(system_prompt=system_prompt, tools=tools)

        # 3. Model Generation
        response = chat.send_message(request.query)

        # Collect tools used if available in the final response parts
        tools_used = []
        for step in chat.history:
            if hasattr(step, 'parts'):
                for part in step.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        tools_used.append(part.function_call.name)

        return {
            "response": response.text,
            "sources": sources if request.use_rag else None,
            "tools_used": list(set(tools_used)) if tools_used else None
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest", response_model=DataIngestResponse)
async def ingest_documents(files: List[UploadFile] = File(...)):
    """
    Upload documents to be ingested into the RAG pipeline vector database.
    """
    temp_dir = os.path.join(settings.CHROMA_PERSIST_DIR, "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)

    saved_files = []

    # Save uploaded files temporarily
    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files.append(file_path)

        # Ingest the directory
        chunks_added = rag.ingest_directory(temp_dir)

        return {
            "status": "success",
            "details": f"Processed {len(files)} files.",
            "chunks_created": chunks_added
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp files
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)

@app.delete("/api/rag/clear")
def clear_vector_store():
    """Clear all data from the vector store."""
    rag.clear()
    return {"status": "success", "message": "Vector store cleared."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
