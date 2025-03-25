import asyncio
import os
import time
from urllib.parse import urlparse
import uuid
import httpx
import idna
import tiktoken
import datetime
import random
from typing import List, Optional, Union
from pydantic_ai.settings import ModelSettings
from pydantic_ai import Agent, RunContext
from pydantic_ai.result import Usage
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolReturnPart

from core.browser_manager import PlaywrightManager
from core.skills.final_response import get_response
from core.utils.message_type import MessageType
from core.utils.openai_msg_parser import AgentConversationHandler, ConversationStorage
from core.utils.custom_exceptions import (
    CustomException, InvalidURLError, PlannerError, 
    BrowserNavigationError, SSAnalysisError, CritiqueError, ToolSequenceError
)

import re
import json
from pathlib import Path
from core.utils.logger import Logger
from core.utils.openai_client import get_client

from core.skills.enter_text_using_selector import bulk_enter_text, entertext
from core.skills.get_dom_with_content_type import get_dom_field_func, get_dom_texts_func
from core.skills.get_url import geturl
from core.skills.open_url import openurl
from core.skills.pdf_text_extractor import extract_text_from_pdf
from core.skills.google_search import google_search
from core.skills.press_key_combination import press_key_combination
from core.skills.click_using_selector import click
from core.skills.hashicorp import get_keys, get_secret

logger = Logger()

def extract_domain(url: str) -> str:
    """Extracts and validates domain from URL with security checks."""
    if not url:
        return ""

    logger.debug(f"Extracting domain from URL: {url}")
    # Pre-validation checks
    url = url.strip()
    if len(url) > 2048:
        raise InvalidURLError("URL exceeds maximum length of 2048 characters")

    try:
        # Protocol normalization
        if not url.startswith(('http://', 'https://')):
            url = f'http://{url}'

        parsed = urlparse(url)
        if not parsed.netloc:
            raise InvalidURLError(f"Empty network location: {url}")

        # Extract hostname component
        hostname = parsed.hostname
        if not hostname:
            raise InvalidURLError(f"Missing hostname: {url}")

        # IDNA normalization and encoding
        try:
            normalized_host = idna.encode(hostname).decode('ascii')
        except idna.IDNAError as e:
            raise InvalidURLError(f"Invalid international domain name: {str(e)}")

        # Security checks
        lower_host = normalized_host.lower()
        if lower_host == 'localhost':
            raise InvalidURLError("Localhost access not permitted")

        # Domain format validation
        if re.search(r"[^a-zA-Z0-9.-]", normalized_host):
            raise InvalidURLError(f"Invalid domain characters: {normalized_host}")

        # www prefix handling
        domain = normalized_host.lower()
        if domain.startswith('www.'):
            domain = domain[4:]

        logger.debug(f"Extracted domain: {domain}")
        
        return domain

    except (ValueError, AttributeError, TypeError) as e:
        raise InvalidURLError(f"URL parsing failure: {str(e)}") from e

def prompt_constructor(inputs):
    """Constructs a prompt string with inputs"""
    return f"Inputs :\n{inputs}"

def extract_tool_interactions(messages):
    """
    Extracts tool calls and their corresponding responses from browser agent messages.
    Returns a formatted string of all tool interactions.
    """
    tool_interactions = {}
    
    for msg in messages:
        # Handle tool calls
        if msg.kind == 'response':
            for part in msg.parts:
                if hasattr(part, 'part_kind') and part.part_kind == 'tool-call':
                    tool_interactions[part.tool_call_id] = {
                        'call': {
                            'tool_name': part.tool_name,
                            'args': part.args_as_dict()  
                        },
                        'response': None
                    }
        
        # Handle tool responses
        elif msg.kind == 'request':
            for part in msg.parts:
                if hasattr(part, 'part_kind') and part.part_kind == 'tool-return':
                    if part.tool_call_id in tool_interactions:
                        tool_interactions[part.tool_call_id]['response'] = {
                            'content': part.content
                        }
    
    # Format tool interactions into a string
    interactions_str = ""
    for tool_id, interaction in tool_interactions.items():
        call = interaction['call']
        response = interaction['response']
        interactions_str += f"Tool Call: {call['tool_name']}\n"
        interactions_str += f"Arguments: {call['args']}\n"
        if response:
            interactions_str += f"Response: {response['content']}\n"
        interactions_str += "---\n"
    
    return interactions_str

def filter_dom_messages(messages):
    """
    Filter message history to replace all DOM responses with placeholder text.
    """
    DOM_TOOLS = {'get_dom_text', 'get_dom_fields'}
    filtered_messages = []
    
    for msg in messages:
        if isinstance(msg, ModelRequest) and msg.parts:
            part = msg.parts[0]
            if (hasattr(part, 'part_kind') and 
                part.part_kind == 'tool-return' and
                part.tool_name in DOM_TOOLS):
                
                # Create new ToolReturnPart with modified content
                new_part = ToolReturnPart(
                    tool_name=part.tool_name,
                    content="DOM successfully fetched",
                    tool_call_id=part.tool_call_id,
                    timestamp=part.timestamp,
                    part_kind='tool-return'
                )
                # Create new ModelRequest with modified part
                filtered_messages.append(ModelRequest(
                    parts=[new_part],
                    kind='request'
                ))
            else:
                filtered_messages.append(msg)
        else:
            filtered_messages.append(msg)
    
    return filtered_messages

class Orchestrator:
    MAX_STEP_RETRIES = 3
    STEP_RETRY_BACKOFF_BASE = 2
    MAX_RETRIES = 3
    AGENT_TIMEOUT = 30

    def __init__(self, input_mode: str = "GUI_ONLY", no_crit: bool = False) -> None:
        """
        Initialize the Orchestrator with critique mode configuration
        
        Args:
            input_mode (str): Input mode for the orchestrator ("GUI_ONLY" or "API")
            no_crit (bool): Flag to determine if critique should be disabled (default: True)
        """
        self.browser_manager = None
        self.shutdown_event = asyncio.Event()
        self.input_mode = input_mode
        self.client = None  # Will be set during async_init
        self.browser_agent = None
        self.critique_agent = None
        self.explainer_agent = None
        self.planner_agent = None
        self.no_crit = no_crit
        self.conversation_handler = AgentConversationHandler()

        # Initialize conversation_storage without job_id (will be set during async_init)
        self.conversation_storage = None
        self.browser_initialized = asyncio.Event()
        self.terminate = False
        self.response_handler = None
        self.raw_browser_history = []
        self.async_init_done = False
        self.message_histories = {
            'planner': [],
            'browser': [],
            'critique': [] if not no_crit else []
        }
        self.cumulative_tokens = {
            'planner': {'total': 0, 'request': 0, 'response': 0},
            'browser': {'total': 0, 'request': 0, 'response': 0}, 
            'critique': {'total': 0, 'request': 0, 'response': 0}
        }
        self.iteration_counter = 0
        self.job_id = None
        self.current_url = None
        self.ss_enabled = False  # Disable screenshot by default
        self.current_domain = None
        self.notification_queue = None
        self.include_ss = False  # Disable screenshots
        self.bb_live_url = None

    
            
    def update_token_usage(self, agent_type: str, usage: Usage):
        self.cumulative_tokens[agent_type]['total'] += usage.total_tokens
        self.cumulative_tokens[agent_type]['request'] += usage.request_tokens 
        self.cumulative_tokens[agent_type]['response'] += usage.response_tokens

    def log_token_usage(self, agent_type: str, usage: Usage, step: Optional[int] = None):
        self.update_token_usage(agent_type, usage)
        step_info = f" (Step {step})" if step is not None else ""
        logger.debug(
                f"""
                \nToken Usage for {agent_type}{step_info}:
                \nIteration tokens: {usage.total_tokens}
                \nCumulative tokens: {self.cumulative_tokens[agent_type]['total']}
                \nTotal request tokens: {self.cumulative_tokens[agent_type]['request']}
                \nTotal response tokens: {self.cumulative_tokens[agent_type]['response']}
                """
        )

    async def async_init(self, job_id: str, start_url: str = "https://google.com"):
        """Initialize a new session context with improved error handling"""
        try:
            logger.info("Initializing browser session", extra={
                "job_id": job_id,
                "start_url": start_url
            })

            # 1. Initialize job_id and validate
            if not job_id:
                raise ValueError("job_id is required for initialization")
            self.job_id = str(job_id)
            logger.debug(f"job_id: {self.job_id}")

            # 2. Initialize conversation storage
            try:
                self.conversation_storage = ConversationStorage(job_id=self.job_id)
            except Exception as storage_error:
                raise RuntimeError(f"Failed to initialize conversation storage: {str(storage_error)}") from storage_error
        
            # 3. Set and validate URL
            try:
                self.current_url = start_url
                self.current_domain = extract_domain(self.current_url)
                logger.info(f"Current URL set to {self.current_url}")
                logger.debug(f"Domain set to: {self.current_domain}")
            except InvalidURLError as url_error:
                raise ValueError(f"Invalid URL provided: {str(url_error)}") from url_error

            # 4. Initialize browser manager with start_url
            if not self.browser_manager:
                try:
                    self.browser_manager = await self.initialize_browser_manager(start_url=start_url)
                    if not self.browser_manager:
                        raise RuntimeError("Browser manager initialization failed")
                except Exception as browser_error:
                    raise RuntimeError(f"Failed to initialize browser manager: {str(browser_error)}") from browser_error

            # 5. Initialize client and agents
            try:
                
                from core.utils.init_client import initialize_client
                self.client, model_instance = await initialize_client()
                self.initialize_agents(model_instance)
            except Exception as agent_error:
                raise RuntimeError(f"Failed to initialize client and agents: {str(agent_error)}") from agent_error

            self.async_init_done = True
            logger.debug("Async initialization completed successfully")

        except ValueError as ve:
            logger.error(f"Validation error during initialization: {str(ve)}")
            await self.emergency_cleanup()
        except RuntimeError as re:
            logger.error(f"Runtime error during initialization: {str(re)}")
            # Attempt cleanup if browser manager was partially initialized
            await self.emergency_cleanup()
        except Exception as e:
            logger.error(f"Unexpected error during initialization: {str(e)}", exc_info=True)
            await self.emergency_cleanup()

    def initialize_agents(self, model_instance) -> None:
        """
        Create and store agent objects as attributes of the Orchestrator using the provided model instance.
        """
        try:
            # Import the necessary prompts and agent definitions
            from core.agents.browser_agent import BA_SYS_PROMPT, BA_Deps
            from core.agents.planner_agent import PA_SYS_PROMPT, PLANNER_AGENT_OP, NCPA_SYS_PROMPT, NCPA_OP
            from core.agents.critique_agent import CA_SYS_PROMPT, CritiqueOutput
            from core.agents.explainer_agent import EXPLAINER_SYS_PROMPT, ExplainerOutput

            # Initialize Explainer Agent
            self.explainer_agent = Agent(
                model=model_instance,
                system_prompt=EXPLAINER_SYS_PROMPT,
                name="Explainer Agent",
                retries=2,
                model_settings=ModelSettings(temperature=0.2),
                result_type=ExplainerOutput
            )
            logger.info("Explainer Agent initialized successfully.")

            # Initialize Browser Agent
            BA_agent = Agent(
                model=model_instance,
                system_prompt=BA_SYS_PROMPT,
                deps_type=BA_Deps,
                name="Browser Agent",
                retries=3,
                model_settings=ModelSettings(temperature=0.5),
            )
            logger.info("Browser Agent initialized successfully.")

            # BA Tools
            @BA_agent.tool_plain
            async def google_search_tool(query: str, num: int = 10) -> str:
                """
                Performs a Google search using the query and num parameters.
                """
                return await google_search(query=query, num=num)

            @BA_agent.tool
            async def bulk_enter_text_tool(ctx: RunContext[BA_Deps], entries) -> str:
                """
                This function enters text into multiple DOM elements using a bulk operation.
                """
                return await bulk_enter_text(bc=ctx.deps.pm, entries=entries)

            @BA_agent.tool
            async def enter_text_tool(ctx: RunContext[BA_Deps], entry) -> str:
                """
                Enters text into a DOM element identified by a CSS selector.
                """
                bc = ctx.deps.pm
                return await entertext(bc=bc, entry=entry)

            @BA_agent.tool
            async def get_dom_text(ctx: RunContext[BA_Deps], prompt: str) -> str:
                """Get text content from the DOM"""
                return await get_dom_texts_func(bc=ctx.deps.pm)

            @BA_agent.tool
            async def get_dom_fields(ctx: RunContext[BA_Deps], prompt: str) -> str:
                """Get form fields from the DOM"""
                return await get_dom_field_func(bc=ctx.deps.pm, current_step=ctx.deps.current_step, info=prompt, agent=self.explainer_agent)

            @BA_agent.tool
            async def get_url(ctx: RunContext[BA_Deps]) -> str:
                """Returns the full URL of the current page"""
                return await geturl(bc=ctx.deps.pm)

            @BA_agent.tool
            async def click_tool(ctx:RunContext[BA_Deps], selector: str, wait_before_execution: float = 0.0) -> str:
                """Executes a click action on the element matching the given query selector"""
                return await click(bc=ctx.deps.pm, selector=selector, wait_before_execution=wait_before_execution)

            @BA_agent.tool
            async def open_url_tool(ctx:RunContext[BA_Deps], url: str, timeout:int = 3) -> str:
                """Opens the specified URL in the browser."""
                return await openurl(bc=ctx.deps.pm, url=url, timeout=timeout)

            @BA_agent.tool
            async def extract_text_from_pdf_tool(ctx:RunContext[BA_Deps], pdf_url: str) -> str:
                """Extracts the text content from a PDF file available at the specified URL."""
                return await extract_text_from_pdf(bc=ctx.deps.pm, pdf_url=pdf_url)

            @BA_agent.tool
            async def press_key_combination_tool(ctx:RunContext[BA_Deps], keys: str) -> str:
                """Presses the specified key combination in the browser."""
                return await press_key_combination(bc=ctx.deps.pm, key_combination=keys)
            
            @BA_agent.tool_plain
            async def get_keys_tool() -> str:
                """
                Retrieves the keys available in the HashiCorp vault.
                """
                return await get_keys()

            @BA_agent.tool_plain
            async def get_secret_tool(key: str) -> str:
                """
                Retrieves the secret value for the specified key from the HashiCorp vault.
                """
                return await get_secret(key=key)
            
            self.browser_agent = BA_agent

            # Initialize Critique Agent if needed
            if not self.no_crit:
                self.critique_agent = Agent(
                    model=model_instance,
                    system_prompt=CA_SYS_PROMPT,
                    name="Critique Agent",
                    retries=3,
                    model_settings=ModelSettings(temperature=0.5),
                    result_type=CritiqueOutput,
                    result_tool_name='final_response',
                    result_tool_description='Synthesizes web automation results into a comprehensive final answer addressing the clients original query.'
                )
                logger.info("Critique Agent initialized successfully.")

            # Initialize Planner Agent
            if self.no_crit:
                self.planner_agent = Agent(
                    model=model_instance,
                    system_prompt=NCPA_SYS_PROMPT,
                    name="Planner Agent",
                    retries=3,
                    model_settings=ModelSettings(temperature=0.5),
                    result_type=NCPA_OP
                )
                logger.info("No-critique Planner Agent initialized successfully.")
            else:
                self.planner_agent = Agent(
                    model=model_instance,
                    system_prompt=PA_SYS_PROMPT,
                    name="Planner Agent",
                    retries=3,
                    model_settings=ModelSettings(temperature=0.5),
                    result_type=PLANNER_AGENT_OP
                )
                logger.info("Planner Agent initialized successfully.")
            
            logger.info("All agents have been initialized successfully.")
        except Exception as e:
            logger.error("Error initializing agents", exc_info=True)
            raise
    
    async def handle_context_limit_error(self):
        error_msg = "Context length exceeded. The conversation history is too long to continue."
        logger.error(error_msg)
        await self.browser_manager.notify_user(
            error_msg,
            message_type=MessageType.ERROR
        )
        await self.notify_client(error_msg, MessageType.ERROR)

        final_response = "Task could not be completed due to conversation length limitations. Please try breaking down your request into smaller steps."
        await self.notify_client(final_response, MessageType.FINAL)
        if self.response_handler:
            await self.response_handler(final_response)
        await self.cleanup()
        return final_response
    
    async def handle_step_failure(self, error_msg: str):
        final_msg = f"Step execution failed permanently: {error_msg}"
        logger.error(final_msg)
        await self.notify_client(final_msg, MessageType.ERROR)
        await self.cleanup()
        raise CustomException(final_msg)
    
    async def handle_agent_error(self, agent_type: str, error: Exception):
        error_msg = f"{agent_type.capitalize()} failed after retries: {str(error)}"
        logger.error(error_msg)
        await self.notify_client(error_msg, MessageType.ERROR)
        await self.cleanup()
        raise CustomException(error_msg)

    async def handle_browser_error(self, error: Exception):
        error_msg = f"Browser operation failed: {str(error)}"
        logger.error(error_msg)
        await self.notify_client(error_msg, MessageType.ERROR)
        # Special cleanup for browser resources
        if self.browser_manager:
            await self.browser_manager.emergency_cleanup()
        raise BrowserNavigationError(error_msg)

    def set_response_handler(self, handler):
        self.response_handler = handler

    async def reset_state(self):
        """Reset state without affecting termination status."""
        # Preserve terminate flag for cleanup logic
        original_terminate = self.terminate
        
        # Reset other states
        if not self.job_id:
            self.conversation_handler = AgentConversationHandler()
            self.conversation_storage = ConversationStorage()
            self.message_histories = {
                'planner': [],
                'browser': [],
                'critique': [] if not self.no_crit else []
            }
    
        self.iteration_counter = 0
        # Restore terminate flag if it was set
        self.terminate = original_terminate
    
    async def initialize_browser_manager(self, start_url: str = "https://google.com"):
        logger.debug(f"Initializing browser manager with start URL: {start_url}")
        if self.input_mode == "API":
            browser_manager = PlaywrightManager(gui_input_mode=False, take_screenshots=False, headless=False, job_ID=self.job_id, start_url=start_url)
            self.bb_live_url = browser_manager.bb_live_url
        else:
            browser_manager = PlaywrightManager(gui_input_mode="GUI_ONLY", start_url=start_url)
        self.browser_manager = browser_manager
        await self.browser_manager.async_initialize()
        self.browser_initialized.set()
        logger.info(f"Browser manager initialized : {browser_manager}")
        return browser_manager
    
    async def notify_client(self, message: str, message_type: MessageType):
        """Send a message to the client-specific notification queue with step count."""
        if self.input_mode == "GUI_ONLY":
            return
        if hasattr(self, "notification_queue") and self.notification_queue:
            sanitized_message = self.sanitize_message(message)
            logger.info(f"Sanitized message: {sanitized_message}")
            notification_data = {
                "message": sanitized_message, 
                "type": message_type.value,
                "step_count": self.iteration_counter  # Include iteration counter
            }
            self.notification_queue.put(notification_data)
        else:
            logger.warn("No notification queue attached. Skipping client notification.")

    async def _update_current_url(self):
        """Updates URL and checks for domain changes with improved error handling"""
        try:
            if self.browser_manager:
                try:
                    page = await self.browser_manager.get_current_page()
                    new_url = page.url
                    if new_url != self.current_url:
                        new_domain = extract_domain(new_url)
                        if new_domain != self.current_domain:
                            logger.info(f"Domain changed to {new_domain}")
                            self.current_domain = new_domain
                        self.current_url = new_url
                except BrowserNavigationError as e:
                    # Convert browser navigation errors to a format critique agent can understand
                    error_msg = str(e)
                    logger.error(f"Critical browser error: {error_msg}")                    
                    raise BrowserNavigationError(f"Browser session error: {error_msg}")
                    
        except Exception as e:
            logger.error("URL update failed", error=str(e))
            raise BrowserNavigationError(f"URL update failed: {str(e)}") from e
        
    async def run(self, command):
        cleanup_done = False
        execution_lock = asyncio.Lock()  # Add a lock to prevent concurrent execution

        try:
            async with execution_lock:  # Ensure only one execution path
                if not self.browser_manager:
                    self.browser_manager = await self.initialize_browser_manager()

                try:
                    logger.info(f"Running {'No-Critique ' if self.no_crit else ''}Loop with User Query: {command}")

                    if self.browser_manager:
                        await self.browser_manager.notify_user(
                            command,
                            message_type=MessageType.USER_QUERY
                        )

                    current_date = datetime.datetime.now().strftime("%B %d, %Y")
                    
                    
                    # Initialize PA_prompt based on critique mode
                    if self.no_crit:
                        PA_prompt = (
                            f"User Query : {command}\n"
                            f"Current URL : {self.current_url}\n"
                            f"Current Date : {current_date}\n"
                            "Tool Response : None\n"
                            "Tool Interactions : None\n"
                        )
                    else:
                        PA_prompt = (
                            f"User Query : {command}\n"
                            "Feedback : None\n"
                            f"Current URL : {self.current_url}\n"
                            f"Current Date : {current_date}"
                        )

                    self.iteration_counter = 0
                    
                    while not self.terminate:
                        step_retry_count = 0
                        step_success = False

                        while not step_success and step_retry_count < self.MAX_STEP_RETRIES:
                            try:
                                self.iteration_counter += 1
                                logger.info(f"________Iteration {self.iteration_counter}________")

                                # Planner Execution
                                try:
                                    planner_agent = self.planner_agent
                                    planner_response = await planner_agent.run(
                                        user_prompt=prompt_constructor(PA_prompt),
                                        message_history=self.message_histories['planner']
                                    )
                                    self.conversation_handler.add_planner_message(planner_response, prompt_constructor(PA_prompt), NCPA = self.no_crit)
                                    self.message_histories['planner'].extend(planner_response.new_messages())

                                    logger.info(f"Planner Response: {planner_response.new_messages()}")

                                    plan_data = planner_response.data
                                    
                                    logger.info(f"Plan:, {plan_data}")
                                    logger.info(f"Plan:, {plan_data.plan}")
                                    logger.info(f"Next step:, {plan_data.next_step}")
                                    plan = plan_data.plan
                                    c_step = plan_data.next_step
                                    
                                    # Handle termination for no_crit mode
                                    if self.no_crit and planner_response.data.terminate:
                                        final_response = planner_response.data.final_response
                                        await self.browser_manager.notify_user(
                                            f"{final_response}",
                                            message_type=MessageType.ANSWER
                                        )
                                        await self.notify_client(f"{final_response}", MessageType.FINAL)
                                        if self.response_handler:
                                            await self.response_handler(final_response)
                                        self.terminate = True
                                        return final_response

                                    logger.info(f"Initial plan : {plan}")
                                    logger.info(f"Current step : {c_step}")
                                    await self.notify_client(f"Plan Generated: {plan}", MessageType.INFO)
                                    logger.info("Before notify client of current step")
                                    await self.notify_client(f"Current Step: {c_step}", MessageType.INFO)

                                    try:
                                        if self.iteration_counter == 1:
                                            await self.browser_manager.notify_user(
                                                f" {plan}",
                                                message_type=MessageType.PLAN
                                            )
                                        await self.browser_manager.notify_user(
                                            f"{c_step}",
                                            message_type=MessageType.STEP
                                        )
                                    except Exception as e:
                                        logger.error(f"Error in notifying plan to the user : {e}")
                                        self.notify_client(f"Error in planner: {str(e)}", MessageType.ERROR)

                                except Exception as e:
                                    error_str = str(e).lower()
                                    if "context_length_exceeded" in error_str or "maximum context length" in error_str:
                                        return await self.handle_context_limit_error()
                                    await self.handle_agent_error('planner', e)

                                self.log_token_usage(
                                    agent_type='planner',
                                    usage=planner_response._usage,
                                    step=self.iteration_counter
                                )

                                browser_error = None
                                tool_interactions_str = None

                                # Browser Execution
                                BA_prompt = (
                                    f'plan="{plan}" '
                                    f'current_step="{c_step}" '
                                )
                                
                                from core.agents.browser_agent import BA_Deps
                                current_step_deps = BA_Deps(
                                    current_step = c_step,
                                    pm = self.browser_manager
                                )

                                try:
                                    logger.debug("Running browser agent")
                                    history = filter_dom_messages(self.message_histories['browser'])
                                    browser_response = await self.browser_agent.run(
                                        user_prompt=prompt_constructor(BA_prompt),
                                        deps=current_step_deps,
                                        message_history=history
                                    )
                                    
                                    new_messages = browser_response.new_messages()
                                    self.conversation_handler.add_browser_nav_message(new_messages)
                                    self.raw_browser_history = []
                                    self.raw_browser_history = new_messages 

                                    self.message_histories['browser'].extend(new_messages)
                                    tool_interactions_str = extract_tool_interactions(new_messages)

                                    logger.debug(f"All Messages from Browser Agent: {browser_response.all_messages()}")
                                    logger.info(f"Tool Interactions: {tool_interactions_str}")
                                    logger.info(f"Browser Agent Response: {browser_response.data}")
                                    await self._update_current_url()

                                    self.log_token_usage(
                                        agent_type='browser',
                                        usage=browser_response._usage,
                                        step=self.iteration_counter
                                    )

                                except BrowserNavigationError as e:
                                    # Immediately terminate the task with error details
                                    error_msg = f"Browser navigation failed permanently: {str(e)}"
                                    logger.error(error_msg)
                                    await self.browser_manager.notify_user(error_msg, MessageType.ERROR)
                                    await self.notify_client(error_msg, MessageType.ERROR)
                                    
                                    if self.response_handler:
                                        await self.response_handler(f"Task failed: {error_msg}")
                                    
                                    self.terminate = True
                                    return f"Task could not be completed: {error_msg}"
                                
                                except Exception as e:
                                    error_str = str(e).lower()
                                    if "context_length_exceeded" in error_str or "maximum context length" in error_str:
                                        return await self.handle_context_limit_error()

                                    browser_error = str(e)
                                    browser_result = f"Browser Agent Error occurred: {browser_error}"
                                    tool_interactions_str = "Error occurred during tool execution"
                                    
                                    logger.error(f"Browser agent execution error: {browser_result}")
                                    await self.browser_manager.notify_user(
                                        f"Error in browser execution: {browser_error}",
                                        message_type=MessageType.ERROR
                                    )

                                # Critique Agent - only if critique is enabled (no_crit is False)
                                if not self.no_crit:
                                    try:
                                        logger.debug("Running critique agent")
                                        
                                        CA_prompt = (
                                            f'plan="{plan}" '
                                            f'next_step="{c_step}" '
                                            f'tool_response="{browser_response.data}" '
                                            f'tool_interactions="{tool_interactions_str}" '
                                            f'ss_analysis="SS analysis not available"'
                                            f'browser_error="{browser_error if browser_error else "None"}"'
                                        )

                                        critique_response = await self.critique_agent.run(
                                            user_prompt=prompt_constructor(CA_prompt),
                                            message_history=self.message_histories['critique']
                                        )
                                        logger.debug(f"Calling add_critique_message from Orchestrator")
                                        self.conversation_handler.add_critique_message(critique_response, prompt_constructor(CA_prompt))
                                        self.message_histories['critique'].extend(critique_response.new_messages())

                                        critique_data = critique_response.data
                                        logger.info(f"Critique Feedback: {critique_data.feedback}")
                                        logger.info(f"Critique Response: {critique_data.final_response}")
                                        logger.info(f"Critique Terminate: {critique_data.terminate}")
                                        
                                        self.log_token_usage(
                                            agent_type='critique',
                                            usage=critique_response._usage,
                                            step=self.iteration_counter
                                        )

                                        if critique_data.terminate:
                                            # Generate final_response if missing
                                            if not critique_data.final_response:
                                                # Use current context to generate final response
                                                final_response = await get_response(
                                                    plan=plan,
                                                    browser_response=browser_response.data,
                                                    current_step=c_step
                                                )
                                                logger.info(f"Programmatically generated final response: {final_response}")
                                            else:
                                                final_response = critique_data.final_response

                                            # Save the conversation history
                                            openai_messages = self.conversation_handler.get_full_conversation()
                                            self.conversation_storage.save_conversation(openai_messages, prefix="task")
                                            
                                            # Notify and terminate
                                            await self.browser_manager.notify_user(
                                                final_response,
                                                message_type=MessageType.ANSWER,
                                            )
                                            await self.notify_client(final_response, MessageType.FINAL)

                                            if self.response_handler:
                                                await self.response_handler(final_response)
                                            self.terminate = True
                                            return final_response
                                        else:
                                           
                                            PA_prompt = (
                                                f"User Query : {command}\n"
                                                f"Feedback : {critique_data.feedback}\n"
                                                f"Current URL : {self.current_url}\n"
                                                f"Current Date : {current_date}\n"
                                            )
                                            await self.notify_client(
                                                f"Feedback: {critique_data.feedback}",
                                                MessageType.INFO
                                            )

                                    except Exception as e:
                                        error_str = str(e).lower()
                                        if "context_length_exceeded" in error_str or "maximum context length" in error_str:
                                            return await self.handle_context_limit_error()
                                        await self.handle_agent_error('critique', e)
                                else:
                                    # Update PA_prompt for no_crit mode
                                    PA_prompt = (
                                        f"User Query : {command}\n"
                                        f"Current URL : {self.current_url}\n"
                                        f"Tool Response : {browser_response.data}\n"
                                        f"Current Date : {current_date}"
                                        f"Tool Interactions : {tool_interactions_str}\n"
                                    )

                                # Save conversation history
                                openai_messages = self.conversation_handler.get_full_conversation()
                                self.conversation_storage.save_conversation(openai_messages, prefix="task")

                                step_success = True

                            except Exception as step_error:
                                step_retry_count += 1
                                error_msg = f"Error in execution step {self.iteration_counter}.{step_retry_count}: {str(step_error)}"
                                backoff_time = min(self.STEP_RETRY_BACKOFF_BASE ** step_retry_count + random.uniform(0, 1), 10)
                                
                                logger.error(f"{error_msg} - Retrying in {backoff_time:.1f}s", exc_info=True)
                                await self.browser_manager.notify_user(
                                    f"{error_msg} - Retrying in {backoff_time:.1f}s",
                                    message_type=MessageType.ERROR
                                )
                                await self.notify_client(
                                    f"{error_msg} - Retrying in {backoff_time:.1f}s", 
                                    MessageType.ERROR
                                )

                                await asyncio.sleep(backoff_time)
                                if step_retry_count >= self.MAX_STEP_RETRIES:
                                    await self.handle_step_failure(error_msg)
                                    return "Task failed due to repeated step errors"

                        if not step_success:
                            await self.handle_step_failure("Maximum step retries exceeded")
                            return "Task aborted"
                    
                except asyncio.CancelledError:
                    logger.info("Orchestrator task cancelled by client")
                    self.terminate = True
                    raise

                except Exception as e:
                    error_msg = f"Critical Error in orchestrator: {str(e)}"
                    await self.notify_client(f"Error in Orchestrator : {str(e)}", MessageType.ERROR)
                    logger.error(error_msg, exc_info=True)
                    if self.browser_manager:
                        await self.browser_manager.notify_user(error_msg, MessageType.ERROR)
                    raise

                finally:
                    if not cleanup_done:
                        try:
                            await self.cleanup()
                            cleanup_done = True
                            self.terminate = True  # Ensure termination is set
                            return  # Exit immediately after cleanup
                        except Exception as cleanup_error:
                            logger.error(f"Error during cleanup: {cleanup_error}")
                            # Don't re-raise to avoid triggering another cleanup

        except Exception as outer_error:
            if not cleanup_done:
                try:
                    await self.cleanup()
                    cleanup_done = True
                except Exception as final_cleanup_error:
                    logger.error(f"Final cleanup error: {final_cleanup_error}")
            raise outer_error  # Re-raise the original error         

    async def start(self):
        logger.debug("Starting the orchestrator")
        await self.async_init(job_id="OPENED_THROUGH_GUI")
        if self.input_mode == "GUI_ONLY":
            browser_context = await self.browser_manager.get_browser_context()
            await browser_context.expose_function('process_task', self.receive_command) # type: ignore
        await self.wait_for_exit()

    async def execute_command(self, command: str, start_url: Optional[str] = None) -> str:
        """
        Execute a command using either critique or no-critique mode based on initialization
        
        Args:
            command (str): The command to execute
            start_url (Optional[str]): Starting URL for the command
            
        Returns:
            str: The final response from command execution
        """
        logger.info(f"Executing command with no_crit={self.no_crit}")
        
        return await self.run(command)
        
    async def receive_command(self, command: str):
        """Process commands with state reset"""
        await self.reset_state()
        
        return await self.execute_command(command)

    async def emergency_cleanup(self):          
        """Emergency cleanup for browser resources when normal cleanup fails"""
        logger.warn("Initiating emergency cleanup")
        
        try:
            if self.browser_manager:
                try:
                    
                    # Close browserbase connection if exists
                    if hasattr(self.browser_manager, 'browserbase') and self.browser_manager.browserbase:
                        try:
                            await self.browser_manager.browserbase.close()
                            logger.debug("Closed browserbase connection")
                        except Exception as bb_error:
                            logger.error(f"Failed to close browserbase: {str(bb_error)}")
                    
                    # Close browser context
                    if hasattr(self.browser_manager, '_browser_context') and self.browser_manager._browser_context:
                        try:
                            await self.browser_manager._browser_context.close()
                            logger.debug("Closed browser context")
                        except Exception as context_error:
                            logger.error(f"Failed to close browser context: {str(context_error)}")
                    
                    # Close browser instance
                    if hasattr(self.browser_manager, '_browser') and self.browser_manager._browser:
                        try:
                            await self.browser_manager._browser.close()
                            logger.debug("Closed browser instance")
                        except Exception as browser_error:
                            logger.error(f"Failed to close browser: {str(browser_error)}")
                    
                    # Stop playwright
                    if hasattr(self.browser_manager, '_playwright') and self.browser_manager._playwright:
                        try:
                            await self.browser_manager._playwright.stop()
                            logger.debug("Stopped playwright")
                        except Exception as playwright_error:
                            logger.error(f"Failed to stop playwright: {str(playwright_error)}")
                    
                except Exception as bm_error:
                    logger.error(f"Error during browser manager cleanup: {str(bm_error)}")
                finally:
                    self.browser_manager = None
            
            # Clear other resources
            self.browser_initialized.clear()
            self.terminate = True
            
            logger.info("Emergency cleanup completed")
            
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {str(e)}")

    async def wait_for_exit(self):
        await self.shutdown_event.wait()

    async def shutdown(self):
        if self.browser_manager:
            await self.browser_manager.stop_playwright()

    async def cleanup(self):
        if hasattr(self, '_cleanup_in_progress') and self._cleanup_in_progress:
            logger.info("Cleanup already in progress, skipping duplicate cleanup")
            return

        self._cleanup_in_progress = True
        
        try:          

            if self.browser_manager:
                await self.browser_manager.stop_playwright()
                self.browser_manager = None
                
            self.terminate = True
            self.browser_initialized.clear()
            
            if self.input_mode != "GUI_ONLY" or not self.job_id:
                self.shutdown_event.set()

            await self.reset_state()
            
            logger.info("Session ended")

        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}", exc_info=True)
            await self.emergency_cleanup()
        finally:
            self._cleanup_in_progress = False
            self.terminate = True

    def sanitize_message(self, message: str) -> str:
        """Sanitize message to remove sensitive information."""
        sensitive_patterns = [
            # Patterns for '=' and ':' separators
            r'(password[=:]\s*)([^\s]+)',
            r'(username[=:]\s*)([^\s]+)',
            r'(credential[=:]\s*)([^\s]+)',
            r'(api_key[=:]\s*)([^\s]+)',
            r'(token[=:]\s*)([^\s]+)',
            r'(password\[)([^\]]+)(\])',
            r'(username\[)([^\]]+)(\])',
            r'(credential\[)([^\]]+)(\])',
            r'(api_key\[)([^\]]+)(\])',
            r'(token\[)([^\]]+)(\])',
            r'(secret[=:]\s*)([^\s]+)',
            r'(key[=:]\s*)([^\s]+)',
            r'(private_key[=:]\s*)([^\s]+)',
            r'(public_key[=:]\s*)([^\s]+)',
            r'(phone[=:]\s*)([^\s]+)',
            r'(phone_number[=:]\s*)([^\s]+)',
            r'(ssn[=:]\s*)([^\s]+)',
            r'(credit_card[=:]\s*)([^\s]+)',
            r'(card_number[=:]\s*)([^\s]+)',
        ]
        
        sanitized = message
        for pattern in sensitive_patterns:
            # For square bracket patterns, preserve the brackets
            if r'\[' in pattern:
                sanitized = re.sub(pattern, r'\1*****\3', sanitized, flags=re.IGNORECASE)
            else:
                sanitized = re.sub(pattern, r'\1*****', sanitized, flags=re.IGNORECASE)
        
        return sanitized