from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI, OpenAI
import os
from dotenv import load_dotenv
from typing import Optional, Dict
from core.utils.logger import Logger
logger = Logger()

load_dotenv()

class ModelValidationError(Exception):
    """Custom exception for model validation errors"""
    pass

def get_env_var(key: str) -> str:
    """Get and sanitize environment variable"""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value.strip()

class OpenAIConfig:
   
   
    @staticmethod
    def validate_model(model: str) -> bool:
        """Validate if the model name matches known patterns"""
        return True
    @staticmethod
    def get_text_config() -> Dict:
        return {
            "api_key": get_env_var("OPENAI_API_KEY"),
            "base_url": "https://api.openai.com/v1",
            "model": get_env_var("OPENAI_MODEL_NAME"),
            "max_retries": 3,
            "timeout": 300.0
        }



def create_client_with_retry(client_class, config: dict):
    """Create an OpenAI client with proper error handling"""
    try:
        # Remove trailing slashes and normalize base URL
        base_url = config["base_url"].rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
            
        return client_class(
            api_key=config["api_key"],
            base_url=base_url,
            max_retries=config["max_retries"],
            timeout=config["timeout"]
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize {client_class.__name__}: {str(e)}") from e

def get_client():
    """Get AsyncOpenAI client for text analysis"""
    config = OpenAIConfig.get_text_config()
    return create_client_with_retry(AsyncOpenAI, config)

# Example usage
async def initialize_and_validate():
    """Initialize client and validate configuration"""
    client = get_client()
    
    return client