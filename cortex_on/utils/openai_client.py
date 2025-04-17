from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
    client = AsyncOpenAI(api_key=api_key, max_retries=3, timeout=10000)
    return client 