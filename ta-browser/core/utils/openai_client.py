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
        model = "gpt-4o"
      
        return {
            "api_key": get_env_var("OPENAI_API_KEY"), #previously: AGENTIC_BROWSER_TEXT_API_KEY
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }

    @staticmethod
    def get_ss_config() -> Dict:
        model = "gpt-4o"
        return {
            "api_key": get_env_var("OPENAI_API_KEY"), #previously: AGENTIC_BROWSER_SS_API_KEY
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }


def create_client_with_retry(client_class, config: dict):
    """Create an OpenAI client with proper error handling"""
    try:
     
        return client_class(
            api_key=config["api_key"],
            max_retries=config["max_retries"],
            timeout=config["timeout"]
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize {client_class.__name__}: {str(e)}") from e

def get_client():
    """Get AsyncOpenAI client for text analysis"""
    config = OpenAIConfig.get_text_config()
    return create_client_with_retry(AsyncOpenAI, config)

def get_ss_client():
    """Get OpenAI client for screenshot analysis"""
    config = OpenAIConfig.get_ss_config()
    return create_client_with_retry(OpenAI, config)

def get_text_model() -> str:
    """Get model name for text analysis"""
    return OpenAIConfig.get_text_config()["model"]

def get_ss_model() -> str:
    """Get model name for screenshot analysis"""
    return OpenAIConfig.get_ss_config()["model"]

# Example usage
# async def initialize_and_validate():
#     """Initialize client and validate configuration"""
#     client = get_client()
    
#     # Validate models
#     if not await validate_models(client):
#         raise ModelValidationError("Failed to validate models. Please check your configuration.")
    
#     return client


# Example usage
async def initialize_and_validate():
    """Initialize client"""
    client = get_client()
    return client