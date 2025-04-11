import os
from typing import Protocol, Any, Dict, Type
from abc import ABC, abstractmethod
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.openai_client import create_client_with_retry as create_openai_client, AsyncOpenAI
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from core.utils.logger import Logger

logger = Logger()

# Configuration
DEFAULT_TEXT_MODEL = "gpt-4o"
TEXT_MODEL_ENV_VAR = "AGENTIC_BROWSER_TEXT_MODEL"
FORCE_MODEL_ENV_VAR = "FORCE_DIRECT_MODEL"

class ModelConfig(Protocol):
    api_key: str
    model_name: str
    max_retries: int
    timeout: float

class BaseModelProvider(ABC):
    @abstractmethod
    def get_client(self) -> Any:
        pass
    
    @abstractmethod
    def create_model(self, model_name: str) -> Any:
        pass

class AnthropicProvider(BaseModelProvider):
    def get_client(self) -> Any:
        return create_anthropic_client(AsyncAnthropic, self._get_config())
    
    def create_model(self, model_name: str) -> AnthropicModel:
        client = self.get_client()
        return AnthropicModel(model_name=model_name, anthropic_client=client)
    
    def _get_config(self) -> ModelConfig:
        return {
            "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "model_name": "claude-3-5-sonnet-20241022",
            "max_retries": 3,
            "timeout": 300.0
        }

class OpenAIProvider(BaseModelProvider):
    def get_client(self) -> Any:
        return create_openai_client(AsyncOpenAI, self._get_config())
    
    def create_model(self, model_name: str) -> OpenAIModel:
        client = self.get_client()
        return OpenAIModel(model_name=model_name, openai_client=client)
    
    def _get_config(self) -> ModelConfig:
        return {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model_name": "gpt-4o-mini",
            "max_retries": 3,
            "timeout": 300.0
        }

class ModelFactory:
    _providers: Dict[str, Type[BaseModelProvider]] = {
        'claude': AnthropicProvider,
        'gpt': OpenAIProvider
    }
    
    @classmethod
    def get_provider(cls, model_name: str) -> BaseModelProvider:
        provider_type = 'claude' if model_name.lower().startswith('claude') else 'gpt'
        return cls._providers[provider_type]()

class ModelManager:
    def __init__(self):
        self.logger = Logger()
    
    def _get_model_name(self) -> str:
        return os.getenv(TEXT_MODEL_ENV_VAR, DEFAULT_TEXT_MODEL)
    
    def _get_force_model(self) -> str:
        return os.getenv(FORCE_MODEL_ENV_VAR, "")
    
    def _extract_client(self, model_instance: Any) -> Any:
        for client_type in ['anthropic_client', 'openai_client']:
            if hasattr(model_instance, client_type):
                return getattr(model_instance, client_type)
        raise ValueError("Model instance does not have a valid client")
    
    async def initialize(self) -> tuple[Any, Any]:
        """
        Initialize and return the client and model instance
        """
        try:
            force_model = self._get_force_model()
            
            if force_model:
                self.logger.info(f"Direct model initialization enabled: {force_model}")
                provider = ModelFactory.get_provider(force_model)
                model_instance = provider.create_model(force_model)
                client_instance = self._extract_client(model_instance)
                return client_instance, model_instance
            
            model_name = self._get_model_name()
            provider = ModelFactory.get_provider(model_name)
            model_instance = provider.create_model(model_name)
            client_instance = self._extract_client(model_instance)
            
            self.logger.info("Client and model instance initialized successfully")
            return client_instance, model_instance
            
        except Exception as e:
            self.logger.error(f"Error initializing client: {str(e)}", exc_info=True)
            raise

# Singleton instance
model_manager = ModelManager()

# Public interface
async def initialize_client() -> tuple[Any, Any]:
    """
    Public interface for initializing the client and model
    """
    return await model_manager.initialize() 