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
        model = get_env_var("AGENTIC_BROWSER_TEXT_MODEL")
        # if not OpenAIConfig.validate_model(model):
        #     raise ModelValidationError(
        #         f"Invalid model: {model}. Must match one of the patterns: "
        #         f"{', '.join(OpenAIConfig.VALID_MODEL_PATTERNS)}"
        #     )
        
        return {
            "api_key": get_env_var("OPENAI_API_KEY"), #previously: AGENTIC_BROWSER_TEXT_API_KEY
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }

    @staticmethod
    def get_ss_config() -> Dict:
        model = get_env_var("AGENTIC_BROWSER_TEXT_MODEL")
        return {
            "api_key": get_env_var("OPENAI_API_KEY"), #previously: AGENTIC_BROWSER_SS_API_KEY
            "model": model,
            "max_retries": 3,
            "timeout": 300.0
        }

# async def validate_models(client: AsyncOpenAI) -> bool:
#     """Validate that configured models are available"""
#     try:
#         available_models = await client.models.list()
#         available_model_ids = [model.id for model in available_models.data]
        
#         text_model = get_text_model()
#         ss_model = get_ss_model()
        
#         if text_model not in available_model_ids:
#             raise ModelValidationError(f"Text model '{text_model}' not available. Available models: {', '.join(available_model_ids)}")
        
#         if ss_model not in available_model_ids:
#             raise ModelValidationError(f"Screenshot model '{ss_model}' not available. Available models: {', '.join(available_model_ids)}")
        
#         return True
#     except Exception as e:
#         logger.error(f"Model validation failed: {str(e)}")
#         return False

def create_client_with_retry(client_class, config: dict):
    """Create an OpenAI client with proper error handling"""
    try:
        # Remove trailing slashes and normalize base URL
        # base_url = config["base_url"].rstrip("/")
        # if not base_url.startswith(("http://", "https://")):
        #     base_url = f"https://{base_url}"
     
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