import os
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.logger import Logger
from core.utils.openai_client import get_client

logger = Logger()

async def initialize_client(model_preference: str = "Anthropic"):
    """
    Initialize and return the Anthropic client and model instance
    
    Args:
        model_preference (str): The model provider to use ("Anthropic" or "OpenAI")
    
    Returns:
        tuple: (client_instance, model_instance)
    """
    try:
        print(f"[INIT_CLIENT] *** Initializing client with model preference: {model_preference} ***")
        logger.info(f"Initializing client with model preference: {model_preference}")
        if model_preference == "Anthropic":
            # Get API key from environment variable
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not found in environment variables")
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
            # Set model name - Claude 3.5 Sonnet
            model_name = os.getenv("ANTHROPIC_MODEL_NAME")
            print(f"[INIT_CLIENT] Using Anthropic model: {model_name}")
            
            # Create client config
            config = {
                "api_key": api_key,
                "model": model_name,
                "max_retries": 3,
                "timeout": 300.0
            }
            
            # Initialize client
            client_instance = create_anthropic_client(AsyncAnthropic, config)
            
            # Create model instance
            from pydantic_ai.models.anthropic import AnthropicModel
            model_instance = AnthropicModel(model_name=model_name, anthropic_client=client_instance)
            
            print(f"[INIT_CLIENT] Anthropic client initialized successfully with model: {model_name}")
            logger.info(f"Anthropic client initialized successfully with model: {model_name}")
            return client_instance, model_instance
        elif model_preference == "OpenAI":
            # Get API key from environment variable
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not found in environment variables")
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            
            # Set model name - GPT-4o
            model_name = os.getenv("OPENAI_MODEL_NAME")
            print(f"[INIT_CLIENT] Using OpenAI model: {model_name}")
            
            # Create client config
            config = {
                "api_key": api_key,
                "model": model_name,
                "max_retries": 3,
                "timeout": 300.0
            }
            
            # Initialize client
            client_instance = get_client()
            
            # Create model instance
            from pydantic_ai.models.openai import OpenAIModel
            model_instance = OpenAIModel(model_name=model_name, openai_client=client_instance)
            
            print(f"[INIT_CLIENT] OpenAI client initialized successfully with model: {model_name}")
            logger.info(f"OpenAI client initialized successfully with model: {model_name}")
            return client_instance, model_instance
        else:
            error_msg = f"Invalid model preference: {model_preference}. Must be 'Anthropic' or 'OpenAI'"
            print(f"[INIT_CLIENT] ERROR: {error_msg}")
            raise ValueError(error_msg)
            
    except Exception as e:
        error_msg = f"Error initializing client: {str(e)}"
        print(f"[INIT_CLIENT] CRITICAL ERROR: {error_msg}")
        logger.error(error_msg, exc_info=True)
        raise