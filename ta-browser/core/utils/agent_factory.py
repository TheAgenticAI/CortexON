import os
from core.utils.anthropic_client import get_client as get_anthropic_client
from pydantic_ai.models.anthropic import AnthropicModel

from core.utils.openai_client import get_client as get_openai_client
from pydantic_ai.models.openai import OpenAIModel

def get_text_model_instance():
    """
    Returns the appropriate text model instance (and its client)
    based on the environment variable AGENTIC_BROWSER_TEXT_MODEL.
    If the model name starts with "claude", then it uses the Anthropic client;
    otherwise, it uses the OpenAI client.
    """
    model_name = os.getenv("AGENTIC_BROWSER_TEXT_MODEL")
    if not model_name:
        raise ValueError("Environment variable AGENTIC_BROWSER_TEXT_MODEL is not set.")

    # If the model name indicates Anthropic (e.g., "claude-3.5-sonnet"), use Anthropic
    if model_name.lower().startswith("claude"):
        
        client = get_anthropic_client()
        return AnthropicModel(model_name=model_name, anthropic_client=client)
        # pass
    else:
        
        client = get_openai_client()
        return OpenAIModel(model_name=model_name, openai_client=client)
