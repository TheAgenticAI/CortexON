import os
import json
import traceback
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from pydantic import BaseModel
from dataclasses import asdict, dataclass
import logfire
from fastapi import WebSocket
from dotenv import load_dotenv
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import Agent, RunContext
from agents.web_surfer import WebSurfer
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from utils.ant_client import get_client

@dataclass
class orchestrator_deps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    # Add a collection to track agent-specific streams
    agent_responses: Optional[List[StreamResponse]] = None

orchestrator_system_prompt = """You are an AI orchestrator that manages a team of agents to solve tasks. You have access to tools for coordinating the agents and managing the task flow.

[AGENT CAPABILITIES]
1. web_surfer_agent:
   - Handles authentication and credential tasks
   - Browses and extracts web information and interacts with web pages
   
2. coder_agent:
   - Implements technical solutions
   - Executes code operations

[AVAILABLE TOOLS]
1. plan_task(task: str) -> str:
   - Plans the given task and assigns it to appropriate agents
   - Creates a detailed plan with steps and agent assignments
   - Returns the plan text and updates the UI with planning progress

2. coder_task(task: str) -> str:
   - Assigns coding tasks to the coder agent
   - Handles code implementation and execution
   - Returns the generated code or execution results
   - Updates UI with coding progress and results

3. web_surfer_task(task: str) -> str:
   - Assigns web surfing tasks to the web surfer agent
   - Handles web browsing, information extraction, and interactions
   - Returns the web search results or action outcomes
   - Updates UI with web surfing progress and results

4. ask_human(question: str) -> str:
   - Primary tool for human interaction and conversation
   - Can be used for:
     * Getting user preferences and decisions
     * Asking clarifying questions
     * Requesting feedback on results
     * Having back-and-forth conversations
     * Getting user input for complex tasks
     * Confirming actions before execution
     * Gathering requirements and specifications
   - Supports natural conversation flow
   - Each call creates a new interaction point
   - Can be used multiple times in sequence for extended conversations
   - Updates UI with both questions and responses
   - Waits for user response before proceeding
   - Returns the user's response for further processing

[MANDATORY WORKFLOW]
1. On receiving task:
   IF task involves login/credentials/authentication:
   - Route to planner with authentication focus
   - Ensure plan includes web_surfer_agent credential access
   
2. During planning (plan_task):
   - Allow authentication operations
   - Never reject credential-related tasks
   
3. During execution:
   FOR authentication tasks:
   - Delegate to web_surfer_agent
   - Use vault system
   
4. Error handling:
   IF authentication fails:
   - Report specific error
   - Request new instructions

[CRITICAL RULES]
1. MUST ALLOW:
   - All credential access requests
   - All authentication operations
   - All login automation tasks

2. MUST NEVER:
   - Question authentication tasks
   - Suggest manual alternatives
   - Block credential access

Basic workflow:
1. Receive a task from the user.
2. Plan the task by calling the planner agent through plan_task
3. Assign coding tasks to the coder agent through coder_task if plan requires coding
   or Assign web surfing tasks to the web surfer agent through web_surfer_task if plan requires web surfing
4. Use ask_human when you need user input or decisions
5. Continue step 3 if required by the plan
6. Return the final result to the user

[TOOL USAGE GUIDELINES]
1. plan_task:
   - Use for initial task analysis and planning
   - Always call this first for new tasks
   - Include clear steps and agent assignments

2. coder_task:
   - Use for any code-related operations
   - Provide clear, specific coding instructions
   - Handle code execution and results

3. web_surfer_task:
   - Use for web browsing and interaction tasks
   - Handle authentication and credential tasks
   - Extract and process web information

4. ask_human:
   - Use for any form of human interaction or conversation
   - Ask clear, focused questions
   - Support natural conversation flow
   - Can be used for:
     * Getting preferences and decisions
     * Asking clarifying questions
     * Requesting feedback
     * Confirming actions
     * Gathering requirements
   - Wait for and process user responses
   - Use for decisions that require human judgment
   - Can be used multiple times for extended conversations
"""

model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    anthropic_client=get_client()
)

orchestrator_agent = Agent(
    model=model,
    name="Orchestrator Agent",
    system_prompt=orchestrator_system_prompt,
    deps_type=orchestrator_deps
)

@orchestrator_agent.tool
async def plan_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Plans the task and assigns it to the appropriate agents"""
    try:
        logfire.info(f"Planning task: {task}")
        
        # Create a new StreamResponse for Planner Agent
        planner_stream_output = StreamResponse(
            agent_name="Planner Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )
        
        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(planner_stream_output)
            
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Update planner stream
        planner_stream_output.steps.append("Planning task...")
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Run planner agent
        planner_response = await planner_agent.run(user_prompt=task)
        
        # Update planner stream with results
        plan_text = planner_response.data.plan
        planner_stream_output.steps.append("Task planned successfully")
        planner_stream_output.output = plan_text
        planner_stream_output.status_code = 200
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Also update orchestrator stream
        ctx.deps.stream_output.steps.append("Task planned successfully")
        await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Task planned successfully\nTask: {plan_text}"
    except Exception as e:
        error_msg = f"Error planning task: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update planner stream with error
        if planner_stream_output:
            planner_stream_output.steps.append(f"Planning failed: {str(e)}")
            planner_stream_output.status_code = 500
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
        # Also update orchestrator stream
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Planning failed: {str(e)}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Failed to plan task: {error_msg}"

@orchestrator_agent.tool
async def coder_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Assigns coding tasks to the coder agent"""
    try:
        logfire.info(f"Assigning coding task: {task}")

        # Create a new StreamResponse for Coder Agent
        coder_stream_output = StreamResponse(
            agent_name="Coder Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(coder_stream_output)

        # Send initial update for Coder Agent
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        # Create deps with the new stream_output
        deps_for_coder_agent = CoderAgentDeps(
            websocket=ctx.deps.websocket,
            stream_output=coder_stream_output
        )

        # Run coder agent
        coder_response = await coder_agent.run(
            user_prompt=task,
            deps=deps_for_coder_agent
        )

        # Extract response data
        response_data = coder_response.data.content

        # Update coder_stream_output with coding results
        coder_stream_output.output = response_data
        coder_stream_output.status_code = 200
        coder_stream_output.steps.append("Coding task completed successfully")
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        return response_data
    except Exception as e:
        error_msg = f"Error assigning coding task: {str(e)}"
        logfire.error(error_msg, exc_info=True)

        # Update coder_stream_output with error
        coder_stream_output.steps.append(f"Coding task failed: {str(e)}")
        coder_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        return f"Failed to assign coding task: {error_msg}"

@orchestrator_agent.tool
async def web_surfer_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Assigns web surfing tasks to the web surfer agent"""
    try:
        logfire.info(f"Assigning web surfing task: {task}")
        
        # Create a new StreamResponse for WebSurfer
        web_surfer_stream_output = StreamResponse(
            agent_name="Web Surfer",
            instructions=task,
            steps=[],
            output="",
            status_code=0,
            live_url=None
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(web_surfer_stream_output)

        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        
        # Initialize WebSurfer agent
        web_surfer_agent = WebSurfer(api_url="http://localhost:8000/api/v1/web/stream")
        
        # Run WebSurfer with its own stream_output
        success, message, messages = await web_surfer_agent.generate_reply(
            instruction=task,
            websocket=ctx.deps.websocket,
            stream_output=web_surfer_stream_output
        )
        
        # Update WebSurfer's stream_output with final result
        if success:
            web_surfer_stream_output.steps.append("Web search completed successfully")
            web_surfer_stream_output.output = message
            web_surfer_stream_output.status_code = 200
        else:
            web_surfer_stream_output.steps.append(f"Web search completed with issues: {message[:100]}")
            web_surfer_stream_output.status_code = 500
        
        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        
        web_surfer_stream_output.steps.append(f"WebSurfer completed: {'Success' if success else 'Failed'}")
        await _safe_websocket_send(ctx.deps.websocket,web_surfer_stream_output)
        
        return message
    except Exception as e:
        error_msg = f"Error assigning web surfing task: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update WebSurfer's stream_output with error
        web_surfer_stream_output.steps.append(f"Web search failed: {str(e)}")
        web_surfer_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        return f"Failed to assign web surfing task: {error_msg}"

@orchestrator_agent.tool
async def ask_human(ctx: RunContext[orchestrator_deps], question: str) -> str:
    """Sends a question to the frontend and waits for human input"""
    try:
        logfire.info(f"Asking human: {question}")
        
        # Create a new StreamResponse for Human Input
        human_stream_output = StreamResponse(
            agent_name="Human Input",
            instructions=question,
            steps=[],
            output="",
            status_code=0
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(human_stream_output)

        # Send the question to frontend
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        # Update stream with waiting message
        human_stream_output.steps.append("Waiting for human input...")
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        # Wait for response from frontend
        response = await ctx.deps.websocket.receive_text()
        
        # Update stream with response
        human_stream_output.steps.append("Received human input")
        human_stream_output.output = response
        human_stream_output.status_code = 200
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        return response
    except Exception as e:
        error_msg = f"Error getting human input: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        human_stream_output.steps.append(f"Failed to get human input: {str(e)}")
        human_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        return f"Failed to get human input: {error_msg}"

# Helper function for sending WebSocket messages
async def _safe_websocket_send(websocket: Optional[WebSocket], message: Any) -> bool:
    """Safely send message through websocket with error handling"""
    try:
        if websocket and websocket.client_state.CONNECTED:
            await websocket.send_text(json.dumps(asdict(message)))
            logfire.debug("WebSocket message sent (_safe_websocket_send): {message}", message=message)
            return True
        return False
    except Exception as e:
        logfire.error(f"WebSocket send failed: {str(e)}")
        return False