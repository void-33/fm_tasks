import json
from google import genai
from google.genai import types
from openai import OpenAI
from app.core.config import settings
from app.schemas.models import RecipeExtraction

gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

ollama_client = OpenAI(
    api_key="EMPTY", 
    base_url=settings.vllm_api_base
)

# Tool definition
def get_current_weather(location: str) -> str:
    """Returns the current weather in a given location. Use this when asked about weather."""
    return f"The weather in {location} is 72F and sunny."

def get_gemini_response(message: str, context: str = "", temperature: float = 0.7, structured: bool = False):
    if not gemini_client:
        raise ValueError("GEMINI_API_KEY not configured.")
        
    system_instruction = "You are a highly capable AI assistant."
    if context:
        system_instruction += f"\n\nHere is relevant context to answer the user's question:\n{context}\n\nUse this context to inform your answer."
        
    config_args = {
        "temperature": temperature,
        "system_instruction": system_instruction,
    }
    
    if structured:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = RecipeExtraction
    else:
        # Provide tools if not asking for structured output
        config_args["tools"] = [get_current_weather]
        
    config = types.GenerateContentConfig(**config_args)
    
    response = gemini_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=message,
        config=config
    )
    
    reply = response.text
    structured_data = None
    
    if structured and reply:
        try:
            structured_data = json.loads(reply)
        except Exception:
            pass
            
    # Handle function calls if any tool was invoked
    if response.function_calls and not structured:
        call = response.function_calls[0]
        if call.name == "get_current_weather":
            # Extract arguments and call the function
            args = call.args
            weather_result = get_current_weather(**args)
            
            # For a full tool-calling flow, we would append the function response 
            # to the history and call the model again. Here we demonstrate handling it.
            reply = f"I used the tool '{call.name}' to check for you: {weather_result}"
            
    return reply, structured_data

def get_ollama_response(message: str, context: str = "", temperature: float = 0.7):
    system_msg = "You are a highly capable AI assistant."
    if context:
        system_msg += f"\n\nContext:\n{context}"
        
    try:
        response = ollama_client.chat.completions.create(
            model="qwen2.5:0.5b",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": message}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return f"Error contacting Ollama backend: {str(e)}", None
