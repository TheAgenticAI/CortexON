import os
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.openai_client import create_client_with_retry as create_openai_client, AsyncOpenAI
from core.utils.logger import Logger
import agent_factory


logger = Logger()


async def initialize_client():
    """
    Initialize and return the client and model instance using agent_factory
    
    Returns:
        tuple: (client_instance, model_instance)
    """
    try:
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




