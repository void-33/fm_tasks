"""LLM Manager for connecting to Gemini API."""

import json
from typing import Any, Dict, List, Optional, Type
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import BaseModel
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with Google's Gemini API."""

    def __init__(self):
        """Initialize the Gemini client using settings."""
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. API calls will fail.")

        genai.configure(api_key=settings.GEMINI_API_KEY)

        # Configure model parameters
        self.generation_config = GenerationConfig(
            temperature=settings.TEMPERATURE,
            top_p=settings.TOP_P,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        )

        # Initialize default model
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=self.generation_config,
        )

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text from a prompt."""
        model = self.model
        if system_prompt:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=self.generation_config,
            )

        response = model.generate_content(prompt)
        return response.text

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        system_prompt: Optional[str] = None
    ) -> BaseModel:
        """Generate structured JSON output validated against a Pydantic model."""
        config = GenerationConfig(
            temperature=settings.TEMPERATURE,
            top_p=settings.TOP_P,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=response_schema
        )

        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=config,
        )

        response = model.generate_content(prompt)

        # Parse the JSON string into the Pydantic model
        try:
            result_dict = json.loads(response.text)
            return response_schema(**result_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse structured output: {e}\nRaw output: {response.text}")
            raise

    def get_chat_session(self, system_prompt: Optional[str] = None, tools: Optional[List[Any]] = None):
        """Get an interactive chat session, optionally with tools."""
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=self.generation_config,
            tools=tools or []
        )
        return model.start_chat(enable_automatic_function_calling=tools is not None and len(tools) > 0)


# Initialize a global instance
llm_client = LLMClient()
