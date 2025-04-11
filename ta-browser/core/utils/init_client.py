import os
from typing import Tuple, Any, Protocol, Dict
from abc import ABC, abstractmethod
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.openai_client import create_client_with_retry as create_openai_client, AsyncOpenAI
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from core.utils.logger import Logger

logger = Logger()


Models = ["gpt-4o", "claude-3-5-sonnet-20241022"]
# Configuration
DEFAULT_TEXT_MODEL = "gpt-4o"
TEXT_MODEL_ENV_VAR = Models[1]  #"AGENTIC_BROWSER_TEXT_MODEL"
FORCE_DIRECT_MODEL_ENV_VAR = ""           #"anthropic" # by fast api we can change this model type

# Model-specific configurations
FORCE_ANTHROPIC_MODEL_NAME = "claude-3-5-sonnet-20241022"  # by fast api we can change this model name
FORCE_OPENAI_MODEL_NAME = "gpt-4o-mini"   # by fast api we can change this model name
MAX_RETRIES = 3
TIMEOUT = 300.0

class ModelConfig(Protocol):
    api_key: str
    model_name: str
    max_retries: int
    timeout: float

class BaseModelProvider(ABC):
    @abstractmethod
    def get_client(self, model_name: str) -> Any:
        pass
    
    @abstractmethod
    def create_model(self, model_name: str) -> Any:
        pass

class AnthropicProvider(BaseModelProvider):
    def get_client(self, model_name: str) -> Any:
        config = self._get_config(model_name)
        self._validate_api_key(config["api_key"], "ANTHROPIC_API_KEY")
        return create_anthropic_client(AsyncAnthropic, config)
    
    def create_model(self, model_name: str) -> AnthropicModel:
        client = self.get_client(model_name)
        return AnthropicModel(model_name=model_name, anthropic_client=client)
    
    def _get_config(self, model_name: str) -> Dict:
        return {
            "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "model_name": model_name,
            "max_retries": MAX_RETRIES,
            "timeout": TIMEOUT
        }
    
    def _validate_api_key(self, api_key: str, env_var_name: str) -> None:
        if not api_key:
            raise ValueError(f"API key not found. Please set the {env_var_name} environment variable.")

class OpenAIProvider(BaseModelProvider):
    def get_client(self, model_name: str) -> Any:
        config = self._get_config(model_name)
        self._validate_api_key(config["api_key"], "OPENAI_API_KEY")
        return create_openai_client(AsyncOpenAI, config)
    
    def create_model(self, model_name: str) -> OpenAIModel:
        client = self.get_client(model_name)
        return OpenAIModel(model_name=model_name, openai_client=client)
    
    def _get_config(self, model_name: str) -> Dict:
        return {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model_name": model_name,
            "max_retries": MAX_RETRIES,
            "timeout": TIMEOUT
        }
    
    def _validate_api_key(self, api_key: str, env_var_name: str) -> None:
        if not api_key:
            raise ValueError(f"API key not found. Please set the {env_var_name} environment variable.")

class ModelFactory:
    _providers = {
        'claude': AnthropicProvider(),
        'gpt': OpenAIProvider()
    }
    
    @classmethod
    def get_provider(cls, model_name: str) -> BaseModelProvider:
        if model_name.lower().startswith('claude'):
            return cls._providers['claude']
        return cls._providers['gpt']

class DirectModelInitializer:
    def __init__(self, model_type: str):
        self.model_type = model_type
        self.logger = Logger()
        self.config = self._get_config()
    
    def _get_config(self) -> ModelConfig:
        if self.model_type == "anthropic":
            return {
                "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                "model_name": FORCE_ANTHROPIC_MODEL_NAME,
                "max_retries": MAX_RETRIES,
                "timeout": TIMEOUT
            }
        return {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model_name": FORCE_OPENAI_MODEL_NAME,
            "max_retries": MAX_RETRIES,
            "timeout": TIMEOUT
        }
    
    def initialize(self) -> Tuple[Any, Any]:
        if not self.config["api_key"]:
            raise ValueError(f"API key not found. Please set the {'ANTHROPIC_API_KEY' if self.model_type == 'anthropic' else 'OPENAI_API_KEY'} environment variable.")
        
        if self.model_type == "anthropic":
            client = create_anthropic_client(AsyncAnthropic, self.config)
            model = AnthropicModel(model_name=self.config["model_name"], anthropic_client=client)
        else:
            client = create_openai_client(AsyncOpenAI, self.config)
            model = OpenAIModel(model_name=self.config["model_name"], openai_client=client)
        
        self.logger.info(f"Initialized directly with {self.model_type} model override.")
        return client, model

class ModelClientExtractor:
    @staticmethod
    def extract(model_instance: Any) -> Any:
        for client_type in ['anthropic_client', 'openai_client']:
            if hasattr(model_instance, client_type):
                return getattr(model_instance, client_type)
        raise ValueError("Model instance does not have a valid client")

def get_text_model_instance() -> Any:
    """
    Returns the appropriate text model instance based on environment variables
    """
    model_name = os.getenv(TEXT_MODEL_ENV_VAR, DEFAULT_TEXT_MODEL)
    provider = ModelFactory.get_provider(model_name)
    return provider.create_model(model_name)

async def initialize_client() -> Tuple[Any, Any]:
    """
    Initialize and return the client and model instance
    """
    try:
        force_model = os.getenv(FORCE_DIRECT_MODEL_ENV_VAR)
        
        if force_model:
            logger.info(f"Direct model initialization enabled: {force_model}")
            return DirectModelInitializer(force_model).initialize()
        
        model_instance = get_text_model_instance()
        client_instance = ModelClientExtractor.extract(model_instance)
        
        logger.info("Client and model instance initialized successfully")
        return client_instance, model_instance
        
    except Exception as e:
        logger.error(f"Error initializing client: {str(e)}", exc_info=True)
        raise




