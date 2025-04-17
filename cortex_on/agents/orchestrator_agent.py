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
from pydantic_ai.usage import UsageLimits
from pydantic_ai import Agent, RunContext
from agents.web_surfer import WebSurfer
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from agents.deep_research_agent import deep_research_agent, deep_research_deps
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

3. deep_research_agent:
   - Conducts comprehensive research on any topic
   - Performs iterative searches to gather in-depth information
   - Synthesizes findings into detailed reports with citations
   - Excellent for tasks requiring thorough investigation and analysis

[MANDATORY WORKFLOW]
1. On receiving task:
   IF task involves login/credentials/authentication:
   - Route to planner with authentication focus
   - Ensure plan includes web_surfer_agent credential access
   
   IF task involves comprehensive research or in-depth information gathering:
   - Consider using deep_research_agent for thorough investigation
   
2. During planning (plan_task):
   - Allow authentication operations
   - Never reject credential-related tasks
   - Identify research-intensive tasks for deep_research_agent
   
3. During execution:
   FOR authentication tasks:
   - Delegate to web_surfer_agent
   - Use vault system
   
   FOR deep research tasks:
   - Delegate to deep_research_agent
   - Allow sufficient time for thorough investigation

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

Basic worflow:
1. Receive a task from the user.
2. Plan the task by calling the planner agent through plan task
3. Assign coding tasks to the coder agent through coder task if plan requires coding
   or Assign web surfing tasks to the web surfer agent through web_surfer_task if plan requires web surfing
   or Assign deep research tasks to the deep research agent through deep_research_task if plan requires comprehensive research
4. Continue step 3 if required by the plan
5. Return the final result to the user
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
async def deep_research_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Assigns deep research tasks to the deep research agent"""
    try:
        logfire.info(f"Starting deep research: {task}")
        
        # Create a new StreamResponse for Deep Research Agent
        research_stream_output = StreamResponse(
            agent_name="Deep Research Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )
        
        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(research_stream_output)
            
        # Send initial update for Deep Research Agent
        await _safe_websocket_send(ctx.deps.websocket, research_stream_output)
        
        # Update deep research stream
        research_stream_output.steps.append("Initializing deep research...")
        await _safe_websocket_send(ctx.deps.websocket, research_stream_output)
        
        # Setup storage path for this research
        import uuid
        research_id = str(uuid.uuid4())
        base_dir = os.path.abspath(os.path.dirname(__file__))
        storage_path = os.path.join(base_dir, "research_data", research_id)
        os.makedirs(storage_path, exist_ok=True)
        
        # Create deps for deep research agent
        deps_for_research_agent = deep_research_deps(
            websocket=ctx.deps.websocket,
            stream_output=research_stream_output,
            storage_path=storage_path
        )
        
        usage_limits=UsageLimits(
            request_limit=150,         
        )
        
        # Run deep research agent
        research_response = await deep_research_agent.run(
            user_prompt=task,
            deps=deps_for_research_agent,
            usage_limits=usage_limits
        )
        
        # Extract response data, handle both dict and string return types
        if hasattr(research_response.data, 'report'):
            research_report = research_response.data.report
        elif isinstance(research_response.data, dict) and 'report' in research_response.data:
            research_report = research_response.data['report']
        else:
            research_report = str(research_response.data)
        
        # Update research_stream_output with results
        research_stream_output.output = research_report
        research_stream_output.status_code = 200
        research_stream_output.steps.append("Deep research completed successfully")
        await _safe_websocket_send(ctx.deps.websocket, research_stream_output)
        
        return research_report
    except Exception as e:
        error_msg = f"Error performing deep research: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update research_stream_output with error
        if research_stream_output:
            research_stream_output.steps.append(f"Deep research failed: {str(e)}")
            research_stream_output.status_code = 500
            await _safe_websocket_send(ctx.deps.websocket, research_stream_output)
            
        # Also update orchestrator stream
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Deep research failed: {str(e)}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Failed to perform deep research: {error_msg}"

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