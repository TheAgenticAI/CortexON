import os
from typing import Tuple, Union
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from utils.ant_client import get_client as get_anthropic_client
from utils.openai_client import get_client as get_openai_client

def initialize_client() -> Tuple[Union[AnthropicModel, OpenAIModel], str]:
    """
    Initialize and return the appropriate client and model instance based on environment configuration
    
    Returns:
        tuple: (model_instance, provider_name)
    """
    provider = os.getenv("AI_PROVIDER", "anthropic").lower()
    
    if provider == "anthropic":
        model_name = os.getenv("ANTHROPIC_MODEL_NAME")
        if not model_name:
            raise ValueError("ANTHROPIC_MODEL_NAME not found in environment variables")
            
        client = get_anthropic_client()
        model = AnthropicModel(model_name=model_name, anthropic_client=client)
        return model, "anthropic"
        
    elif provider == "openai":
        model_name = os.getenv("OPENAI_MODEL_NAME")
        if not model_name:
            raise ValueError("OPENAI_MODEL_NAME not found in environment variables")
            
        client = get_openai_client()
        model = OpenAIModel(model_name=model_name, openai_client=client)
        return model, "openai"
        
    else:
        raise ValueError(f"Unsupported AI provider: {provider}") 