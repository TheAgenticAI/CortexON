from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    client = AsyncOpenAI(
        api_key=api_key,
        max_retries=3,
        timeout=10000
    )
    return client 