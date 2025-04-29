#Standard library imports
import os
import json
from typing import List, Optional, Dict, Any, Union, Tuple
import uuid
from dataclasses import asdict, dataclass

#Third party imports
import logfire
from fastapi import WebSocket
from dotenv import load_dotenv
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerHTTP

#Local imports
from utils.stream_response_format import StreamResponse
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

5. planner_agent_update(completed_task: str) -> str:
   - Updates the todo.md file to mark a task as completed
   - Takes the description of the completed task as input
   - Returns the updated plan with completed tasks marked
   - Must be called after each agent completes a task

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

4. After each task completion:
   - Call planner_agent_update to mark the task as completed
   - Review the updated plan to determine the next task
   
5. Error handling:
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
4. After each task completion, call planner_agent_update to mark the task as completed
5. Review the updated plan to determine the next task to execute
6. Use ask_human when you need user input or decisions
7. Continue steps 3-6 until all tasks in the plan are completed
8. Return the final result to the user

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

5. planner_agent_update:
   - Call after each task completion to mark it as completed
   - Include which agent performed the task in the description
   - Review the updated plan to determine the next task to execute
   - Format: "Task description (agent_name)"
"""

# Initialize MCP Server
#we can add multiple servers here
#example:
# server1 = MCPServerHTTP(url='http://localhost:8004/sse')  
# server2 = MCPServerHTTP(url='http://localhost:8003/sse')  
server = MCPServerHTTP(url='http://localhost:8002/sse')  

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
   #  mcp_servers=[server],
)

# Human Input Tool attached to the orchestrator agent as a tool
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
            status_code=0,
            message_id=str(uuid.uuid4())
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

async def _safe_websocket_send(socket: WebSocket, message: Any) -> bool:
        """Safely send message through websocket with error handling"""
        try:
            if socket and socket.client_state.CONNECTED:
                await socket.send_text(json.dumps(asdict(message)))
                logfire.debug("WebSocket message sent (_safe_websocket_send): {message}", message=message)
                return True
            return False
        except Exception as e:
            logfire.error(f"WebSocket send failed: {str(e)}")
            return False