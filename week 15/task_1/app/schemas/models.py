from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class IngestRequest(BaseModel):
    text: str = Field(..., description="The text content to ingest")

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the assistant")
    model_type: str = Field(default="gemini", description="Which model to use: 'gemini' or 'ollama'")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    use_rag: bool = Field(default=True, description="Whether to query the vector database for context")
    structured_output: bool = Field(default=False, description="If true, returns the response in a predefined JSON structure")

class ChatResponse(BaseModel):
    reply: str = Field(description="The assistant's text response")
    sources: Optional[List[str]] = Field(default=None, description="Sources used if RAG was enabled")
    structured_data: Optional[Dict[str, Any]] = Field(default=None, description="The parsed JSON if structured_output was requested")

# A sample schema for structured output testing
class RecipeExtraction(BaseModel):
    recipe_name: str
    ingredients: List[str]
    prep_time_minutes: int
