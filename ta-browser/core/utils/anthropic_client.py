from pydantic_ai.models.anthropic import AnthropicModel
from anthropic import AsyncAnthropic
import os
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

def get_env_var(key: str) -> str:
    """Get and sanitize environment variable"""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value.strip()

class AnthropicConfig:
    @staticmethod
    def get_text_config() -> Dict:
        model =  "claude-3-5-sonnet-20241022"    # previously: ANTHROPIC_MODEL_NAME
        
        return {
            "api_key": get_env_var("ANTHROPIC_API_KEY"),
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }

    @staticmethod
    def get_ss_config() -> Dict:
        model =  "claude-3-5-sonnet-20241022"
        
        return {
            "api_key": get_env_var("ANTHROPIC_API_KEY"),
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }

def create_client_with_retry(client_class, config: dict):
    """Create an Anthropic client with proper error handling"""
    try:
        return client_class(
            api_key=config["api_key"],
            max_retries=config["max_retries"],
            timeout=config["timeout"]
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize {client_class.__name__}: {str(e)}") from e

def get_client():
    """Get AsyncAnthropic client for text analysis"""
    config = AnthropicConfig.get_text_config()
    return create_client_with_retry(AsyncAnthropic, config)

def get_ss_client():
    """Get Anthropic client for screenshot analysis"""
    config = AnthropicConfig.get_ss_config()
    return create_client_with_retry(AsyncAnthropic, config)

def get_text_model() -> str:
    """Get model name for text analysis"""
    return AnthropicConfig.get_text_config()["model"]

def get_ss_model() -> str:
    """Get model name for screenshot analysis"""
    return AnthropicConfig.get_ss_config()["model"]

# Example usage
async def initialize_and_validate():
    """Initialize client"""
    client = get_client()
    return client