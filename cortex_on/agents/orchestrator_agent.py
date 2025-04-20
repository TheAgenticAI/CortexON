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
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerHTTP, MCPServerStdio
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from utils.ant_client import get_client
load_dotenv()

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
2. Plan the task by calling the planner agent through plan task
3. Assign coding tasks to the coder agent through coder task if plan requires coding
or Assign web surfing tasks to the web surfer agent through web_surfer_task if plan requires web surfing
4. Continue step 3 if required by the plan
5. Return the final result to the user
"""

# Initialize MCP Server
# server = MCPServerStdio('python', ["-m", "agents.mcp_server"])
server = MCPServerHTTP(url='http://localhost:3001/sse')  

# Initialize Anthropic provider with API key
provider = AnthropicProvider(api_key=os.environ.get("ANTHROPIC_API_KEY"))

model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    provider=provider
)

orchestrator_agent = Agent(
    model=model,
    name="Orchestrator Agent",
    system_prompt=orchestrator_system_prompt,
    deps_type=orchestrator_deps,
    mcp_servers=[server],
)


# @orchestrator_agent.tool
# async def plan_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
#     """Plans the task and assigns it to the appropriate agents"""
#     try:
#         logfire.info(f"Planning task: {task}")

#         # Create a new StreamResponse for Planner Agent
#         planner_stream_output = StreamResponse(
#             agent_name="Planner Agent",
#             instructions=task,
#             steps=[],
#             output="",
#             status_code=0,
#         )

#         # Add to orchestrator's response collection if available
#         if ctx.deps.agent_responses is not None:
#             ctx.deps.agent_responses.append(planner_stream_output)

#         await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)

#         # Update planner stream
#         planner_stream_output.steps.append("Planning task...")
#         await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)

#         # Run planner agent through MCP
#         async with orchestrator_agent.run_mcp_servers():
#             result = await orchestrator_agent.run(
#                 f"Use the plan_task tool to plan: {task}"
#             )
#             plan_text = result.output

#         # Update planner stream with results
#         planner_stream_output.steps.append("Task planned successfully")
#         planner_stream_output.output = plan_text
#         planner_stream_output.status_code = 200
#         await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)

#         # Also update orchestrator stream
#         ctx.deps.stream_output.steps.append("Task planned successfully")
#         await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)

#         return f"Task planned successfully\nTask: {plan_text}"
#     except Exception as e:
#         error_msg = f"Error planning task: {str(e)}"
#         logfire.error(error_msg, exc_info=True)

#         # Update planner stream with error
#         if planner_stream_output:
#             planner_stream_output.steps.append(f"Planning failed: {str(e)}")
#             planner_stream_output.status_code = 500
#             await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)

#         # Also update orchestrator stream
#         if ctx.deps.stream_output:
#             ctx.deps.stream_output.steps.append(f"Planning failed: {str(e)}")
#             await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)

#         return f"Failed to plan task: {error_msg}"


# @orchestrator_agent.tool
# async def coder_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
#     """Assigns coding tasks to the coder agent"""
#     try:
#         logfire.info(f"Assigning coding task: {task}")

#         # Create a new StreamResponse for Coder Agent
#         coder_stream_output = StreamResponse(
#             agent_name="Coder Agent",
#             instructions=task,
#             steps=[],
#             output="",
#             status_code=0,
#         )

#         # Add to orchestrator's response collection if available
#         if ctx.deps.agent_responses is not None:
#             ctx.deps.agent_responses.append(coder_stream_output)

#         # Send initial update for Coder Agent
#         await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

#         # Run coder agent through MCP
#         async with orchestrator_agent.run_mcp_servers():
#             result = await orchestrator_agent.run(
#                 f"Use the code_task tool to implement: {task}"
#             )
#             response_data = result.output

#         # Update coder_stream_output with coding results
#         coder_stream_output.output = response_data
#         coder_stream_output.status_code = 200
#         coder_stream_output.steps.append("Coding task completed successfully")
#         await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

#         return response_data
#     except Exception as e:
#         error_msg = f"Error assigning coding task: {str(e)}"
#         logfire.error(error_msg, exc_info=True)

#         # Update coder_stream_output with error
#         coder_stream_output.steps.append(f"Coding task failed: {str(e)}")
#         coder_stream_output.status_code = 500
#         await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

#         return f"Failed to assign coding task: {error_msg}"


# @orchestrator_agent.tool
# async def web_surfer_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
#     """Assigns web surfing tasks to the web surfer agent"""
#     try:
#         logfire.info(f"Assigning web surfing task: {task}")

#         # Create a new StreamResponse for WebSurfer
#         web_surfer_stream_output = StreamResponse(
#             agent_name="Web Surfer",
#             instructions=task,
#             steps=[],
#             output="",
#             status_code=0,
#             live_url=None,
#         )

#         # Add to orchestrator's response collection if available
#         if ctx.deps.agent_responses is not None:
#             ctx.deps.agent_responses.append(web_surfer_stream_output)

#         await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)

#         # Run web surfer agent through MCP
#         async with orchestrator_agent.run_mcp_servers():
#             result = await orchestrator_agent.run(
#                 f"Use the web_surf_task tool to search: {task}"
#             )
#             message = result.output

#         # Update WebSurfer's stream_output with final result
#         web_surfer_stream_output.steps.append("Web search completed successfully")
#         web_surfer_stream_output.output = message
#         web_surfer_stream_output.status_code = 200
#         await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)

#         web_surfer_stream_output.steps.append("WebSurfer completed: Success")
#         await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)

#         return message
#     except Exception as e:
#         error_msg = f"Error assigning web surfing task: {str(e)}"
#         logfire.error(error_msg, exc_info=True)

#         # Update WebSurfer's stream_output with error
#         web_surfer_stream_output.steps.append(f"Web search failed: {str(e)}")
#         web_surfer_stream_output.status_code = 500
#         await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)

#         return f"Failed to assign web surfing task: {error_msg}"


# # Helper function for sending WebSocket messages
# async def _safe_websocket_send(websocket: Optional[WebSocket], message: Any) -> bool:
#     """Safely send message through websocket with error handling"""
#     try:
#         if websocket and websocket.client_state.CONNECTED:
#             await websocket.send_text(json.dumps(asdict(message)))
#             logfire.debug(f"WebSocket message sent: {message}")
#             return True
#         return False
#     except Exception as e:
#         logfire.error(f"WebSocket send failed: {str(e)}")
#         return False
