"""Tools for the AI assistant to use via function calling."""

import math
from typing import Dict, Any, List

def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression string (e.g., '2 + 2', 'math.sqrt(16)')

    Returns:
        The result of the evaluation as a string.
    """
    try:
        # Use eval with a restricted dictionary containing math functions
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"

def get_weather(location: str) -> str:
    """
    Get the current weather for a specific location.

    Args:
        location: The city and state/country, e.g., 'San Francisco, CA' or 'Tokyo, Japan'

    Returns:
        A string describing the weather.
    """
    # In a real app, this would call a real weather API
    # Since this is a demo, we return mock data based on simple matching
    location = location.lower()
    if "san francisco" in location or "sf" in location:
        return "62°F (17°C) and partly cloudy with a light breeze."
    elif "new york" in location or "nyc" in location:
        return "75°F (24°C) and sunny."
    elif "tokyo" in location:
        return "82°F (28°C) and rainy."
    elif "london" in location:
        return "55°F (13°C) and overcast."
    elif "kathmandu" in location:
        return "78°F (26°C) and clear skies."

    return f"Weather data for {location} is currently unavailable. Ask the user for a major city."

def get_system_time() -> str:
    """
    Get the current system time and date.

    Returns:
        The current date and time as a string.
    """
    from datetime import datetime
    now = datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"


# List of all available tools
# The Gemini SDK can directly extract schemas from Python functions!
AVAILABLE_TOOLS = [
    calculate,
    get_weather,
    get_system_time
]
