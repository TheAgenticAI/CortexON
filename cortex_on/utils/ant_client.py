from pydantic_ai.models.anthropic import AnthropicModel
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")

    client = AsyncAnthropic(api_key=api_key, 
                         max_retries=3,
                         timeout=10000)
    return client



def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=api_key, 
                         max_retries=3,
                         timeout=10000)
    return client

def get_openai_model_instance():
        model_name = os.getenv("OPENAI_MODEL_NAME")
        # Create model instance
        from pydantic_ai.models.openai import OpenAIModel
        model_instance = OpenAIModel(model_name=model_name, openai_client=get_openai_client())
        return model_instance

def get_anthropic_model_instance():
    model_name = os.getenv("ANTHROPIC_MODEL_NAME")
    # Create model instance
    from pydantic_ai.models.anthropic import AnthropicModel
    model_instance = AnthropicModel(model_name=model_name, anthropic_client=get_client())
    return model_instance
