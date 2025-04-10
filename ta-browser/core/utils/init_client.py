import os
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.openai_client import create_client_with_retry as create_openai_client, AsyncOpenAI
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from core.utils.logger import Logger
import agent_factory


logger = Logger()

FORCE_DIRECT_MODEL = os.getenv("FORCE_DIRECT_MODEL", None)

async def initialize_client():
    """
    Initialize and return the client and model instance using agent_factory
    
    Returns:
        tuple: (client_instance, model_instance)
    """
    try:

        if FORCE_DIRECT_MODEL:
            logger.info(f"Direct model initialization enabled: {FORCE_DIRECT_MODEL}")
            if FORCE_DIRECT_MODEL == "anthropic":
                # API key is hardcoded or could be fetched from another config if needed.
                api_key = os.getenv("ANTHROPIC_API_KEY", None)
                model_name = "claude-3-5-sonnet-20241022"
                # model_name = "claude-3-7-sonnet-20250219"
                config = {
                    "api_key": api_key,
                    "model": model_name,
                    "max_retries": 3,
                    "timeout": 300.0
                }
                client_instance = create_anthropic_client(AsyncAnthropic, config)
                
                model_instance = AnthropicModel(model_name=model_name, anthropic_client=client_instance)
                logger.info("Initialized directly with Anthropich model override.")
                return client_instance, model_instance

            elif FORCE_DIRECT_MODEL == "openai":
                api_key = os.getenv("OPENAI_API_KEY", None)
                model_name = "gpt-4o-mini"
                config = {
                    "api_key": api_key,
                    "model": model_name,
                    "max_retries": 3,
                    "timeout": 300.0
                }
                client_instance = create_openai_client(AsyncOpenAI, config)
                model_instance = OpenAIModel(model_name=model_name, openai_client=client_instance)
                logger.info("Initialized directly with OpenAI model override.")
                return client_instance, model_instance
            else:
                logger.info(f"Invalid model name: {FORCE_DIRECT_MODEL}")
                raise ValueError(f"Invalid model name: {FORCE_DIRECT_MODEL}")
            
        '''if force-firect model is not set, get the model instance from agent_factory'''


        # Get the model instance from agent_factory
        model_instance = agent_factory.get_text_model_instance()
        
        # Get the client from the model instance
        if hasattr(model_instance, 'anthropic_client'):
            client_instance = model_instance.anthropic_client
            return client_instance, model_instance
        elif hasattr(model_instance, 'openai_client'):
            client_instance = model_instance.openai_client
            return client_instance, model_instance
        else:
            raise ValueError("Model instance does not have a valid client")
        
        logger.info("Client and model instance initialized successfully")
        return client_instance, model_instance
        
    except Exception as e:
        logger.error(f"Error initializing client: {str(e)}", exc_info=True)
        raise




