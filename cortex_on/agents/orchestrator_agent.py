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
from pydantic_ai.usage import UsageLimits
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerHTTP

#Local imports
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
load_dotenv()
from agents.planner_agent import planner_agent, update_todo_status
from utils.ant_client import get_client

@dataclass
class orchestrator_deps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    # Add a collection to track agent-specific streams
    agent_responses: Optional[List[StreamResponse]] = None


orchestrator_system_prompt = """You are an AI orchestrator that manages a team of agents to solve tasks. You have access to tools for coordinating the agents and managing the task flow.

[CRITICAL RESPONSE REQUIREMENT]
YOU MUST ALWAYS PROVIDE A FINAL RESPONSE TO THE USER. Never return empty or blank responses. Even if tasks fail or encounter errors, you must explain what happened and provide meaningful feedback. Your response should summarize what was accomplished and any relevant information gathered during the process.

<agent_capabilities>
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

</agent_capabilities>

When deciding which service or agent to use:
1. For general code-related tasks: Use coder_agent
2. For general web browsing tasks: Use web_surfer_agent
3. For comprehensive research tasks: Use deep_research_agent
<server_selection_guidelines>

You can use multiple services in sequence for complex tasks

<available_tools>
These are tools directly available to you:
1. plan_task(task: str) -> str:
   - Plans the given task and assigns it to appropriate agents
   - Creates a detailed plan with steps and agent assignments
   - Returns the plan text and updates the UI with planning progress

2. coder_task(task: str) -> str:
   - Assigns coding tasks to the coder agent
   - Handles code implementation and execution
   - Returns the generated code or execution results
   - Updates UI with coding progress and results

4. web_surfer_task(task: str) -> str:
   - Assigns web surfing tasks to the web surfer agent
   - Handles web browsing, information extraction, and interactions
   - Returns the web search results or action outcomes
   - Updates UI with web surfing progress and results

5. deep_research_task(task: str) -> str:
   - Assigns comprehensive research tasks to the deep research agent
   - Conducts iterative searches to gather in-depth information
   - Synthesizes findings into detailed reports with citations
   - Excellent for tasks requiring thorough investigation and analysis
   - Returns comprehensive research reports
   - Updates UI with research progress and findings

6. ask_human(question: str) -> str:
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

7. planner_agent_update(completed_task: str) -> str:
   - Updates the todo.md file to mark a task as completed
   - Takes the description of the completed task as input
   - Returns the updated plan with completed tasks marked
   - Must be called after each agent completes a task

8. server_status_update(server_name: str, status_message: str, progress: float = 0, details: Dict[str, Any] = None) -> str:
   - Sends live updates about external server access to the UI
   - Use when accessing external APIs or MCP servers (like Google Maps, GitHub, etc.)
   - Parameters:
     * server_name: Name of the server (e.g., 'google_maps', 'github')
     * status_message: Short, descriptive status message
     * progress: Progress percentage (0-100)
     * details: Optional detailed information
   - Send frequent updates during lengthy operations
   - Updates the UI in real-time with server interaction progress
   - Call this when:
     * Starting to access a server
     * Making requests to external APIs
     * Receiving responses from external systems
     * Completing server interactions
   - Examples:
     * "Connecting to Google Maps API..."
     * "Fetching location data for New York..."
     * "Processing route information..."
     * "Retrieved map data successfully"


</available_tools>

<servers_available_to_you_with_list_of_their_tools>
These are the servers available to you with list of their tools:

I. MAIN MCP SERVER:
1. coder_task(task: str) -> str:
   - Assigns coding tasks to the coder agent
   - Handles code implementation and execution
   - Returns the generated code or execution results
   - Updates UI with coding progress and results

2. web_surfer_task(task: str) -> str:
   - Assigns web surfing tasks to the web surfer agent
   - Handles web browsing, information extraction, and interactions
   - Returns the web search results or action outcomes
   - Updates UI with web surfing progress and results

3. deep_research_task(task: str) -> str:
   - Assigns deep research tasks to the deep research agent
   - Conducts iterative searches and analysis
   - Synthesizes findings into detailed reports
   - Returns comprehensive research reports with citations
   - Updates UI with research progress and findings

</servers_available_to_you_with_list_of_their_tools>

<mandatory_workflow>
1. ALWAYS start with planning:
   - First action upon receiving any task MUST be to call plan_task
   - This creates a structured plan with clear steps and agent assignments
   - Never skip the planning phase

2. Execute according to plan:
   - Use the generated plan to determine which tools/servers to use
   - Follow the plan's step-by-step breakdown
   - Route tasks to appropriate agents based on plan assignments

3. Task completion tracking:
   - After each task completion, call planner_agent_update to mark progress
   - Review the updated plan to determine next steps
   - Continue until all planned tasks are completed

4. Authentication and credential handling:
   - Route all authentication tasks to web_surfer_agent
   - Use vault system for credential management
   - Never block or question credential access requests

5. Error handling and recovery:
   - Report specific errors when they occur
   - Request new instructions when needed
   - Update plan if tasks cannot be completed as originally planned
   - ALWAYS provide a response explaining what happened, even if errors occur
   - Never leave the user without feedback or results

Basic workflow sequence:
1. Receive task from user
2. MANDATORY: Call plan_task to create detailed execution plan
3. Follow plan step-by-step using appropriate tools:
   - Use coder_task for coding operations
   - Use web_surfer_task for web browsing and authentication
   - Use deep_research_task for comprehensive research operations
   - Use ask_human for user interaction and decisions
4. After each step completion, call planner_agent_update
5. Review updated plan and continue to next step
6. Repeat steps 3-5 until all plan tasks are completed
7. Provide final results to user

[CRITICAL RULES]
1. MUST ALWAYS start with plan_task - no exceptions
2. MUST follow the generated plan structure
3. MUST allow all authentication and credential operations
4. MUST update plan progress after each task completion
5. MUST route tasks to appropriate agents as specified in plan
6. MUST always provide a clear final response when all tasks are completed
</mandatory_workflow>

<final_response_requirements>
When all tasks in the plan are completed, you MUST provide a final summary response that includes:
1. A brief overview of what was accomplished
2. Key results or findings from the executed tasks
3. Any important information gathered during the process
4. Clear indication that the task has been completed successfully

RESPONSE FORMAT:
- Always provide a substantive response, never leave it empty
- Summarize the key outcomes and results
- Use clear, informative language
- Include relevant details from the task execution
- End with a clear completion statement

EXAMPLES:
"I have successfully completed the restaurant search for Garia. Here are the key results: [summary of findings]. The task has been completed successfully."

"The coding task has been finished. I implemented [details of what was built], tested the functionality, and verified the results. All requirements have been met."
</final_response_requirements>

<task_completion_guidelines>
WHEN TO STOP CALLING TOOLS AND PROVIDE FINAL RESPONSE:
1. After all tasks in the plan are marked as completed via planner_agent_update
2. When the user's original request has been fully addressed
3. When you have gathered sufficient information to answer the user's question
4. After completing the main workflow sequence (plan → execute → update → complete)

SIGNS THAT YOU SHOULD PROVIDE A FINAL RESPONSE:
- All plan tasks show [x] completed status
- You have results or information to share with the user
- The requested action has been performed successfully
- You've encountered an error that prevents further progress

ALWAYS REMEMBER:
- Your final response should be a direct message to the user
- Summarize what was accomplished and any key findings
- Do NOT call more tools after providing your final summary
- End with a clear completion statement
</task_completion_guidelines>

<tool_usage_guidelines>

DIRECT ORCHESTRATOR TOOLS:
These tools are directly attached to the orchestrator agent:

1. plan_task(task: str) -> str:
   - MANDATORY first step for any task
   - Creates detailed execution plan with step-by-step breakdown
   - Assigns tasks to appropriate agents
   - Provides structure for the entire workflow
   - Updates UI with planning progress
   - Must be called before using any other tools

2. ask_human(question: str) -> str:
   - Primary tool for human interaction and conversation
   - Use for:
     * Getting user preferences and decisions
     * Asking clarifying questions
     * Requesting feedback on results
     * Having back-and-forth conversations
     * Getting user input for complex tasks
     * Confirming actions before execution
     * Gathering requirements and specifications
   - Supports natural conversation flow
   - Can be used multiple times for extended conversations
   - Updates UI with both questions and responses
   - Waits for user response before proceeding

3. planner_agent_update(completed_task: str) -> str:
   - Updates todo.md file to mark tasks as completed
   - MUST be called after each task completion
   - Takes description of completed task as input
   - Returns updated plan with completion status
   - Enables progress tracking and next step determination
   - Format: "Task description (agent_name)"

[MANDATORY WORKFLOW FOR DEEP RESEARCH]
1. BEFORE assigning ANY task to deep_research_task:
   - You MUST FIRST use ask_human to get specific information
   - Ask targeted questions to narrow research scope
   - Get user preferences on research depth and focus areas
   - This step CANNOT be skipped under any circumstances
   - Example of targeted questions:
     * For a query like "research about credit cards in India":
       - "Are you interested in credit cards for rewards, cashback, travel, fuel, or business?"
       - "Any preferred banks or issuers?"
       - "Monthly income or credit score (approx.)?"
       - "Any specific fees or interest rates you want to avoid?"
       - "New user offers or lifetime free cards preferred?"
   
2. Only AFTER getting user input through ask_human:
   - Then assign the task to deep_research_task
   - Include the additional context from user in the research task
   
3. This sequence is REQUIRED:
   - First: ask_human for targeted questions
   - Second: deep_research_task with enhanced context
   - Never call deep_research_task without prior ask_human


4. server_status_update(server_name: str, status_message: str, progress: float, details: Dict) -> str:
   - Sends live updates about external server access to UI
   - Use when accessing external APIs or MCP servers
   - Provides real-time feedback on server interactions
   - Parameters:
     * server_name: Name of the server being accessed
     * status_message: Short descriptive status message
     * progress: Progress percentage (0-100)
     * details: Optional detailed information
   - Call during lengthy operations for user feedback

SERVER TOOLS GUIDELINES:
These tools are provided by MCP servers and should be used according to the plan:

1. coder_task(task: str) -> str:
   - Provided by main MCP server
   - Use for all code-related operations as specified in plan
   - Handles code implementation, execution, and testing
   - Provide clear, specific coding instructions
   - Returns generated code or execution results
   - Updates UI with coding progress and results
   - Route here when plan specifies coding work

2. web_surfer_task(task: str) -> str:
   - Provided by main MCP server
   - Use for web browsing and interaction tasks as specified in plan
   - Handles authentication and credential operations
   - Extracts and processes web information
   - Performs web page interactions
   - Returns search results or action outcomes
   - Updates UI with web surfing progress
   - Route here when plan specifies web operations or authentication

3. deep_research_task(task: str) -> str:
   - Provided by main MCP server
   - Use for comprehensive research tasks as specified in plan
   - Conducts iterative searches and analysis
   - Synthesizes findings into detailed reports
   - Excellent for tasks requiring thorough investigation
   - Returns comprehensive research reports with citations
   - Updates UI with research progress and findings
   - Route here when plan specifies research operations

EXTERNAL MCP SERVER TOOLS:
<external_mcp_server_tools>

CRITICAL: EXTERNAL SERVER STATUS REPORTING
When using external MCP server tools, you MUST provide detailed status updates using server_status_update:

REQUIRED SEQUENCE FOR EXTERNAL SERVER OPERATIONS:
1. BEFORE calling external tool:
   - Call server_status_update(server_name, "Connecting to server...", 10)
   - Call server_status_update(server_name, "Preparing request...", 30)

2. AFTER calling external tool:
   - Call server_status_update(server_name, "Processing response...", 80)
   - Call server_status_update(server_name, "Operation completed successfully", 100)

EXAMPLE USAGE PATTERN:
```
# Before external tool call
await server_status_update("google-maps", "Connecting to Google Maps API...", 10)
await server_status_update("google-maps", "Preparing location search request...", 30)

# Call external tool
result = await google-maps.places(query="restaurants near Garia")

# After external tool call  
await server_status_update("google-maps", "Processing location data...", 80)
await server_status_update("google-maps", "Successfully retrieved restaurant information", 100)
```

This ensures users see step-by-step progress similar to the planner agent.

EXTERNAL TOOL USAGE:
Call external server tools directly using their full names:
- Format: server-name.tool-name (e.g., google-maps.places, github.search_repositories)
- ALWAYS use server_status_update before and after external tool calls
- Follow the required sequence above for proper user feedback

TOOL USAGE SEQUENCE:
1. ALWAYS start with plan_task
2. Use different server tools based on plan assignments
3. Use ask_human for user interaction when needed
4. Use planner_agent_update after each task completion
5. Use server_status_update for external server operations
6. Repeat steps 2-5 until plan is complete
7. PROVIDE FINAL RESPONSE to user summarizing results

[CRITICAL: AVOID INFINITE LOOPS]
- Do NOT continuously call tools without progress
- After completing all planned tasks, STOP calling tools
- Provide a final summary response to the user
- If you're unsure whether to continue, ask_human for guidance
- Maximum of 10 tool calls per conversation unless user specifically requests more
</tool_usage_guidelines>
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

# Initialize the agent with just the main MCP server for now
# External servers will be added dynamically at runtime
orchestrator_agent = Agent(
    model=model,
    name="Orchestrator Agent",
    system_prompt=orchestrator_system_prompt,
    deps_type=orchestrator_deps,
    mcp_servers=[server],  # Start with just the main server
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

@orchestrator_agent.tool
async def plan_task(ctx: RunContext[orchestrator_deps],task: str) -> str:
        """Plans the task and assigns it to the appropriate agents"""
        try:
            logfire.info(f"Planning task: {task}")
            planner_stream_output = StreamResponse(
                agent_name="Planner Agent",
                instructions=task,
                steps=[],
                output="",
                status_code=0,
                message_id=str(uuid.uuid4())
            )
            
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
            
            return f"Task planned successfully\nTask: {plan_text}"
        except Exception as e:
            error_msg = f"Error planning task: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            # Update planner stream with error
            if 'planner_stream_output' in locals():
                planner_stream_output.steps.append(f"Planning failed: {str(e)}")
                planner_stream_output.status_code = 500
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
            return f"Failed to plan task: {error_msg}"
         
@orchestrator_agent.tool
async def planner_agent_update(ctx: RunContext[orchestrator_deps],completed_task: str) -> str:
        """
        Updates the todo.md file to mark a task as completed and returns the full updated plan.
        """
        try:
            logfire.info(f"Updating plan with completed task: {completed_task}")
            # Create a new StreamResponse for Planner Agent update
            planner_stream_output = StreamResponse(
                agent_name="Planner Agent",
                instructions=f"Update todo.md to mark as completed: {completed_task}",
                steps=[],
                output="",
                status_code=0,
                message_id=str(uuid.uuid4())
            )
            
            # Send initial update
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            # Directly read and update the todo.md file
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            planner_dir = os.path.join(base_dir, "agents", "planner")
            todo_path = os.path.join(planner_dir, "todo.md")
            
            planner_stream_output.steps.append("Reading current todo.md...")
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            # Make sure the directory exists
            os.makedirs(planner_dir, exist_ok=True)
            
            try:
                # Check if todo.md exists
                if not os.path.exists(todo_path):
                    planner_stream_output.steps.append("No todo.md file found. Will create new one after task completion.")
                    await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                    
                    # We'll directly call planner_agent.run() to create a new plan first
                    plan_prompt = f"Create a simple task plan based on this completed task: {completed_task}"
                    plan_response = await planner_agent.run(user_prompt=plan_prompt)
                    current_content = plan_response.data.plan
                else:
                    # Read existing todo.md
                    with open(todo_path, "r") as file:
                        current_content = file.read()
                        planner_stream_output.steps.append(f"Found existing todo.md ({len(current_content)} bytes)")
                        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                # Now call planner_agent.run() with specific instructions to update the plan
                update_prompt = f"""
                Here is the current todo.md content:
                
                {current_content}
                
                Please update this plan to mark the following task as completed: {completed_task}
                Return ONLY the fully updated plan with appropriate tasks marked as [x] instead of [ ].
                """
                
                planner_stream_output.steps.append("Asking planner to update the plan...")
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                updated_plan_response = await planner_agent.run(user_prompt=update_prompt)
                updated_plan = updated_plan_response.data.plan
                
                # Write the updated plan back to todo.md
                with open(todo_path, "w") as file:
                    file.write(updated_plan)
                
                planner_stream_output.steps.append("Plan updated successfully")
                planner_stream_output.output = updated_plan
                planner_stream_output.status_code = 200
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                return updated_plan
                
            except Exception as e:
                error_msg = f"Error during plan update operations: {str(e)}"
                logfire.error(error_msg, exc_info=True)
                
                planner_stream_output.steps.append(f"Plan update failed: {str(e)}")
                planner_stream_output.status_code = 500
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                return f"Failed to update the plan: {error_msg}"
            
        except Exception as e:
            error_msg = f"Error updating plan: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            return f"Failed to update plan: {error_msg}"
         
@orchestrator_agent.tool
async def server_status_update(ctx: RunContext[orchestrator_deps], server_name: str, status_message: str, progress: float = 0, details: Dict[str, Any] = None) -> str:
    """Send status update about an external server to the UI
    
    Args:
        server_name: Name of the server being accessed (e.g., 'google_maps', 'github')
        status_message: Short status message to display
        progress: Progress percentage (0-100)
        details: Optional detailed information about the server status
    """
    try:
        if server_name == 'npx':
            logfire.info(f"Server Initialisation with npx. No requirement of sending update to UI")
            return f"Server Initialisation with npx. No requirement of sending update to UI"

        logfire.info(f"Server status update for {server_name}: {status_message}")
        if ctx.deps.stream_output is None:
            return f"Could not send status update: No stream output available"
            
        # Initialize server_status if needed
        if ctx.deps.stream_output.server_status is None:
            ctx.deps.stream_output.server_status = {}
            
        # Create status update
        status_update = {
            "status": status_message,
            "progress": progress,
            "timestamp": str(uuid.uuid4())  # Generate unique ID for this update
        }
        
        # Add optional details
        if details:
            status_update["details"] = details
            
        # Update stream_output
        ctx.deps.stream_output.server_status[server_name] = status_update
        ctx.deps.stream_output.steps.append(f"Server update from {server_name}: {status_message}")
        
        # Send update to WebSocket
        success = await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        if success:
            return f"Successfully sent status update for {server_name}"
        else:
            return f"Failed to send status update for {server_name}: WebSocket error"
            
    except Exception as e:
        error_msg = f"Error sending server status update: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        return f"Failed to send server status update: {error_msg}"

# deep_research_task is now handled by the MCP server, not as a direct orchestrator tool


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