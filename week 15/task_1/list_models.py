import os
from google import genai
from dotenv import load_dotenv

load_dotenv('.env')

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
try:
    for model in client.models.list():
        if "embed" in model.name.lower() or "embedding" in model.name.lower():
            print(f"Embedding model found: {model.name}")
except Exception as e:
    print(f"Error: {e}")
