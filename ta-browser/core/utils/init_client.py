import os

from openai import AsyncOpenAI
from core.utils.anthropic_client import create_client_with_retry as create_anthropic_client, AsyncAnthropic
from core.utils.logger import Logger
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = Logger()

async def initialize_client():
    """
    Initialize and return the Anthropic client and model instance
    
    Returns:
        tuple: (client_instance, model_instance)
    """
    try:
        # # Get API key from environment variable
        # api_key = os.getenv("ANTHROPIC_API_KEY")
        # if not api_key:
        #     logger.error("ANTHROPIC_API_KEY not found in environment variables")
        #     raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        # # Set model name - Claude 3.5 Sonnet
        # model_name = os.getenv("ANTHROPIC_MODEL_NAME")
        
        # # Create client config
        # config = {
        #     "api_key": api_key,
        #     "model": model_name,
        #     "max_retries": 3,
        #     "timeout": 300.0
        # }
        
        # # Initialize client
        # client_instance = create_anthropic_client(AsyncAnthropic, config)
        
        # # Create model instance
        # from pydantic_ai.models.anthropic import AnthropicModel
        # model_instance = AnthropicModel(model_name=model_name, anthropic_client=client_instance)
        
        # logger.info(f"Anthropic client initialized successfully with model: {model_name}")
        # return client_instance, model_instance
        api_key = os.getenv("AGENTIC_API_KEY")
        base_url = os.getenv("AGENTIC_BASE_URL")
        if not api_key or not base_url:
            raise ValueError("AGENTIC_API_KEY or AGENTIC_BASE_URL not found in environment variables")
        model_name = 'agentic-turbo'
        client = AsyncOpenAI(api_key=api_key, 
                         base_url=base_url,
                         max_retries=3,
                         timeout=10000)
        client_instance = client
        model_openai = OpenAIModel(
            model_name='agentic-turbo',
            provider=OpenAIProvider(
                api_key=os.getenv("AGENTIC_API_KEY"),
                base_url=os.getenv("AGENTIC_BASE_URL"),
            )
        )
        model_instance = model_openai
        return client_instance, model_instance
        
        
    except Exception as e:
        logger.error(f"Error initializing Anthropic client: {str(e)}", exc_info=True)
        raise