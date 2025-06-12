# final_response.py

import os

from core.utils.logger import Logger
logger = Logger()

# Common system prompt for final response
SYSTEM_PROMPT = """
<role>
    - You are a Final Response Agent. Your job is to provide a final response to the user based on the plan, browser response, and current step.
    - You are a part of a multi-agent environment that includes a Planner Agent, Browser Agent, and Critique Agent.
    - The Browser Agent gives the answer and if the Critique Agent thinks the answer is correct, it calls you to provide the final response.
</role>

<understanding_input>
    - You have been provided with the original plan (which is a sequence of steps).
    - The current step parameter is the step that the planner asked the browser agent to perform.
    - The browser response is the response of the browser agent after performing the step.
</understanding_input>

<rules>
    - You need to generate the final answer like an answer to the query and you are forbidden from providing generic stuff like "information has been compiled" etc.
    - If the plan was to compile or generate a report, you need to provide the report in your response.
    - The answer will most likely be inside the Browser Response. But if the Browser Agent has responded like "I have compiled the information successfully" without including the actual information, then you need to tell the Critique Agent that the actual information is missing and you should retry getting the necessary details from the Browser Agent.
    - Your response should strictly be the answer that the user was looking for.
    - When generating a "Compiled report", do not provide it in the form of a literal table. Instead, use a pointwise format with headings and sub-headings.
    - If the response is in the form of a table, you need to convert it into a pointwise format.
</rules>

<output>
    - Provide your response as an answer in a string format.
</output>
"""

def get_final_response_provider():
    """
    Detects the provider based on the environment variable and returns
    a tuple of (provider, client, model).

    This function is similar to your shared get_text_model_instance(), but here
    we also return a provider flag to help us choose the correct API call.
    """
    model_name = os.getenv("ANTHROPIC_MODEL_NAME")
    if not model_name:
        raise ValueError("Environment variable ANTHROPIC_MODEL_NAME is not set.")

    if model_name.lower().startswith("claude"):
        # Anthropic provider
        from core.utils.anthropic_client import get_client as get_anthropic_client
        from pydantic_ai.models.anthropic import AnthropicModel
        client = get_anthropic_client()
        model = AnthropicModel(model_name=model_name, anthropic_client=client)
        provider = "anthropic"
    else:
        # OpenAI provider (default)
        from core.utils.openai_client import get_client as get_openai_client
        from pydantic_ai.models.openai import OpenAIModel
        client = get_openai_client()
        model = OpenAIModel(model_name=model_name, openai_client=client)
        provider = "openai"
    
    return provider, client, model
async def get_response(plan: str, browser_response: str, current_step: str) -> str:
    """
    Generates the final response by selecting the appropriate provider
    and calling its API with the combined prompt.
    """
    provider, client, model = get_final_response_provider()

    # Build the user prompt from the inputs
    user_prompt = (
        f"Plan: {plan}\n\n"
        f"Browser Response: {browser_response}\n\n"
        f"Current Step: {current_step}\n\n"
    )

    if provider == "anthropic":
        # Anthropic uses a different method signature.
        response = await client.messages.create(
            model=model.model_name,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4000,
        )
        # Adjust based on the actual Anthropic response structure.
        response_content = response.content[0].text
    else:
        # Default to OpenAI.
        response = await client.chat.completions.create(
            model=model.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4000,
        )
        # Adjust based on the actual OpenAI response structure.
        response_content = response.choices[0].message.content

    logger.info(f"Final Response: {response_content}")
    return response_content
