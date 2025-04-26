# Standard library imports
import json
import os
import asyncio
import traceback
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import threading

# Third-party imports
from dotenv import load_dotenv
from fastapi import WebSocket
import logfire
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.anthropic import AnthropicModel
from mcp.server.fastmcp import FastMCP

# Local application imports
from agents.code_agent import CoderAgentDeps, coder_agent
from agents.orchestrator_agent import orchestrator_agent, orchestrator_deps
from agents.planner_agent import planner_agent
from agents.web_surfer import WebSurfer
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
from agents.mcp_server import server
load_dotenv()

# Server manager to handle multiple MCP servers
class ServerManager:
    def __init__(self):
        self.servers = {}  # Dictionary to track running servers by port
        self.default_port = 8002 # default port for main MCP server with agents as a tool
    
    def start_server(self, port=None, name=None):
        """Start an MCP server on the specified port"""
        if port is None:
            port = self.default_port
        
        if name is None:
            name = f"mcp_server_{port}"
            
        # Check if server is already running on this port
        if port in self.servers and self.servers[port]['running']:
            logfire.info(f"MCP server already running on port {port}")
            return
        
        # Configure server for this port
        server_instance = FastMCP(name=name, host="0.0.0.0", port=port)
        
        # Track server in our registry
        self.servers[port] = {
            'running': True,
            'name': name,
            'instance': server_instance,
            'thread': None
        }
        
        def run_server():
            logfire.info(f"Starting MCP server '{name}' on port {port}...")
            # Configure the server to use the specified port
            server_instance.run(transport="sse")
        
        # Start in a separate thread
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self.servers[port]['thread'] = thread
        logfire.info(f"MCP server thread started for '{name}' on port {port}")
    
    def get_server(self, port=None):
        """Get the server instance for the specified port"""
        if port is None:
            port = self.default_port
            
        if port in self.servers:
            return self.servers[port]['instance']
        return None

# Initialize the server manager
server_manager = ServerManager()

def start_mcp_server(port=None, name=None):
    """Start an MCP server on the specified port"""
    server_manager.start_server(port=port, name=name)
    #we can add multiple servers here

# For backwards compatibility
def start_mcp_server_in_thread():
    """Start the MCP server in a separate thread (legacy function)"""
    start_mcp_server()

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects and Pydantic models"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, BaseModel):
            # Handle both Pydantic v1 and v2
            if hasattr(obj, 'model_dump'):
                return obj.model_dump()
            elif hasattr(obj, 'dict'):
                return obj.dict()
            # Fallback for any other Pydantic structure
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        return super().default(obj)


def register_tools_for_main_mcp_server(websocket: WebSocket, port=None) -> None:
    """
    Dynamically register MCP server tools with the provided WebSocket.
    This ensures all tools have access to the active WebSocket connection.
    
    Args:
        websocket: The active WebSocket connection
        port: Optional port number to target a specific MCP server
    """
    # Get the appropriate server instance
    server_instance = server_manager.get_server(port)
    if server_instance is None:
        logfire.error(f"No MCP server found on port {port or server_manager.default_port}")
        return
    
    # First, unregister existing tools if they exist
    tool_names = ["plan_task", "code_task", "web_surf_task", "ask_human", "planner_agent_update"]
    for tool_name in tool_names:
        if tool_name in server_instance._tool_manager._tools:
            del server_instance._tool_manager._tools[tool_name]
    
    logfire.info("Registering MCP tools with WebSocket connection")
    
    async def plan_task(task: str) -> str:
        """Plans the task and assigns it to the appropriate agents"""
        try:
            logfire.info(f"Planning task: {task}")
            print(f"Planning task: {task}")
            planner_stream_output = StreamResponse(
                agent_name="Planner Agent",
                instructions=task,
                steps=[],
                output="",
                status_code=0,
                message_id=str(uuid.uuid4())
            )
            
            await _safe_websocket_send(websocket, planner_stream_output)
            
            # Update planner stream
            planner_stream_output.steps.append("Planning task...")
            await _safe_websocket_send(websocket, planner_stream_output)
            
            # Run planner agent
            planner_response = await planner_agent.run(user_prompt=task)
            
            # Update planner stream with results
            plan_text = planner_response.data.plan
            planner_stream_output.steps.append("Task planned successfully")
            planner_stream_output.output = plan_text
            planner_stream_output.status_code = 200
            await _safe_websocket_send(websocket, planner_stream_output)
            
            return f"Task planned successfully\nTask: {plan_text}"
        except Exception as e:
            error_msg = f"Error planning task: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            # Update planner stream with error
            if 'planner_stream_output' in locals():
                planner_stream_output.steps.append(f"Planning failed: {str(e)}")
                planner_stream_output.status_code = 500
                await _safe_websocket_send(websocket, planner_stream_output)
                
            return f"Failed to plan task: {error_msg}"
    
    async def code_task(task: str) -> str:
        """Assigns coding tasks to the coder agent"""
        try:
            logfire.info(f"Assigning coding task: {task}")
            print(f"Assigning coding task: {task}")
            # Create a new StreamResponse for Coder Agent
            coder_stream_output = StreamResponse(
                agent_name="Coder Agent",
                instructions=task,
                steps=[],
                output="",
                status_code=0,
                message_id=str(uuid.uuid4())
            )

            await _safe_websocket_send(websocket, coder_stream_output)

            # Create deps with the new stream_output
            deps_for_coder_agent = CoderAgentDeps(
                websocket=websocket,
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
            await _safe_websocket_send(websocket, coder_stream_output)

            # Add a reminder in the result message to update the plan using planner_agent_update
            response_with_reminder = f"{response_data}\n\nReminder: You must now call planner_agent_update with the completed task description: \"{task} (coder_agent)\""

            return response_with_reminder
        except Exception as e:
            error_msg = f"Error assigning coding task: {str(e)}"
            logfire.error(error_msg, exc_info=True)

            # Update coder_stream_output with error
            if 'coder_stream_output' in locals():
                coder_stream_output.steps.append(f"Coding task failed: {str(e)}")
                coder_stream_output.status_code = 500
                await _safe_websocket_send(websocket, coder_stream_output)

            return f"Failed to assign coding task: {error_msg}"
    
    async def web_surf_task(task: str) -> str:
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
                live_url=None,
                message_id=str(uuid.uuid4())
            )

            await _safe_websocket_send(websocket, web_surfer_stream_output)
            
            # Initialize WebSurfer agent
            web_surfer_agent = WebSurfer(api_url="http://localhost:8000/api/v1/web/stream")
            
            # Run WebSurfer with its own stream_output
            success, message, messages = await web_surfer_agent.generate_reply(
                instruction=task,
                websocket=websocket,
                stream_output=web_surfer_stream_output
            )
            
            # Update WebSurfer's stream_output with final result
            if success:
                web_surfer_stream_output.steps.append("Web search completed successfully")
                web_surfer_stream_output.output = message
                web_surfer_stream_output.status_code = 200

                # Add a reminder to update the plan
                message_with_reminder = f"{message}\n\nReminder: You must now call planner_agent_update with the completed task description: \"{task} (web_surfer_agent)\""
            else:
                web_surfer_stream_output.steps.append(f"Web search completed with issues: {message[:100]}")
                web_surfer_stream_output.status_code = 500
                message_with_reminder = message

            await _safe_websocket_send(websocket, web_surfer_stream_output)
            
            web_surfer_stream_output.steps.append(f"WebSurfer completed: {'Success' if success else 'Failed'}")
            await _safe_websocket_send(websocket, web_surfer_stream_output)
            
            return message_with_reminder
        except Exception as e:
            error_msg = f"Error assigning web surfing task: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            # Update WebSurfer's stream_output with error
            if 'web_surfer_stream_output' in locals():
                web_surfer_stream_output.steps.append(f"Web search failed: {str(e)}")
                web_surfer_stream_output.status_code = 500
                await _safe_websocket_send(websocket, web_surfer_stream_output)
            return f"Failed to assign web surfing task: {error_msg}"
    
    async def planner_agent_update(completed_task: str) -> str:
        """
        Updates the todo.md file to mark a task as completed and returns the full updated plan.
        """
        try:
            logfire.info(f"Updating plan with completed task: {completed_task}")
            print(f"Updating plan with completed task: {completed_task}")
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
            await _safe_websocket_send(websocket, planner_stream_output)
            
            # Directly read and update the todo.md file
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            planner_dir = os.path.join(base_dir, "agents", "planner")
            todo_path = os.path.join(planner_dir, "todo.md")
            
            planner_stream_output.steps.append("Reading current todo.md...")
            await _safe_websocket_send(websocket, planner_stream_output)
            
            # Make sure the directory exists
            os.makedirs(planner_dir, exist_ok=True)
            
            try:
                # Check if todo.md exists
                if not os.path.exists(todo_path):
                    planner_stream_output.steps.append("No todo.md file found. Will create new one after task completion.")
                    await _safe_websocket_send(websocket, planner_stream_output)
                    
                    # We'll directly call planner_agent.run() to create a new plan first
                    plan_prompt = f"Create a simple task plan based on this completed task: {completed_task}"
                    plan_response = await planner_agent.run(user_prompt=plan_prompt)
                    current_content = plan_response.data.plan
                else:
                    # Read existing todo.md
                    with open(todo_path, "r") as file:
                        current_content = file.read()
                        planner_stream_output.steps.append(f"Found existing todo.md ({len(current_content)} bytes)")
                        await _safe_websocket_send(websocket, planner_stream_output)
                
                # Now call planner_agent.run() with specific instructions to update the plan
                update_prompt = f"""
                Here is the current todo.md content:
                
                {current_content}
                
                Please update this plan to mark the following task as completed: {completed_task}
                Return ONLY the fully updated plan with appropriate tasks marked as [x] instead of [ ].
                """
                
                planner_stream_output.steps.append("Asking planner to update the plan...")
                await _safe_websocket_send(websocket, planner_stream_output)
                
                updated_plan_response = await planner_agent.run(user_prompt=update_prompt)
                updated_plan = updated_plan_response.data.plan
                
                # Write the updated plan back to todo.md
                with open(todo_path, "w") as file:
                    file.write(updated_plan)
                
                planner_stream_output.steps.append("Plan updated successfully")
                planner_stream_output.output = updated_plan
                planner_stream_output.status_code = 200
                await _safe_websocket_send(websocket, planner_stream_output)
                
                return updated_plan
                
            except Exception as e:
                error_msg = f"Error during plan update operations: {str(e)}"
                logfire.error(error_msg, exc_info=True)
                
                planner_stream_output.steps.append(f"Plan update failed: {str(e)}")
                planner_stream_output.status_code = 500
                await _safe_websocket_send(websocket, planner_stream_output)
                
                return f"Failed to update the plan: {error_msg}"
            
        except Exception as e:
            error_msg = f"Error updating plan: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            return f"Failed to update plan: {error_msg}"
    
    # Helper function for websocket communication
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
    
    # Now register all the generated tools with the MCP server
    tool_definitions = {
        "plan_task": (plan_task, "Plans the task and assigns it to the appropriate agents"),
        "code_task": (code_task, "Assigns coding tasks to the coder agent"),
        "web_surf_task": (web_surf_task, "Assigns web surfing tasks to the web surfer agent"),
        "planner_agent_update": (planner_agent_update, "Updates the todo.md file to mark a task as completed")
    }
    
    # Register each tool with the specified server instance
    for name, (fn, desc) in tool_definitions.items():
        server_instance._tool_manager.add_tool(fn, name=name, description=desc)
    
    logfire.info(f"Successfully registered {len(tool_definitions)} tools with the MCP server on port {port or server_manager.default_port}")


# Main Orchestrator Class
class SystemInstructor:
    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.stream_output: Optional[StreamResponse] = None
        self.orchestrator_response: List[StreamResponse] = []
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging with proper formatting"""
        logfire.configure(
            send_to_logfire='if-token-present',
            token=os.getenv("LOGFIRE_TOKEN"),
            scrubbing=False,
        )

    async def _safe_websocket_send(self, message: Any) -> bool:
        """Safely send message through websocket with error handling"""
        try:
            if self.websocket and self.websocket.client_state.CONNECTED:
                await self.websocket.send_text(json.dumps(asdict(message)))
                logfire.debug(f"WebSocket message sent: {message}")
                return True
            return False
        except Exception as e:
            logfire.error(f"WebSocket send failed: {str(e)}")
            return False

    async def run(self, task: str, websocket: WebSocket, server_config: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """
        Main orchestration loop with comprehensive error handling
        
        Args:
            task: The task instructions
            websocket: The active WebSocket connection
            server_config: Optional configuration for MCP servers {name: port}
        """
        self.websocket = websocket
        stream_output = StreamResponse(
            agent_name="Orchestrator",
            instructions=task,
            steps=[],
            output="",
            status_code=0,
            message_id=str(uuid.uuid4())
        )
        self.orchestrator_response.append(stream_output)

        # Create dependencies with list to track agent responses
        deps_for_orchestrator = orchestrator_deps(
            websocket=self.websocket,
            stream_output=stream_output,
            agent_responses=self.orchestrator_response  # Pass reference to collection
        )

        try:
            # Initialize system
            await self._safe_websocket_send(stream_output)
            
            # Apply default server configuration if none provided
            if server_config is None:
                server_config = {
                    "main": server_manager.default_port
                }
            
            # Start each configured MCP server
            for server_name, port in server_config.items():
                start_mcp_server(port=port, name=server_name)
                # Register tools for this server
                register_tools_for_main_mcp_server(websocket=self.websocket, port=port)

            # Configure orchestrator_agent to use the main MCP server port
            async with orchestrator_agent.run_mcp_servers():
                orchestrator_response = await orchestrator_agent.run(
                    user_prompt=task,
                    deps=deps_for_orchestrator
                )
            stream_output.output = orchestrator_response.output
            stream_output.status_code = 200
            logfire.debug(f"Orchestrator response: {orchestrator_response.output}")
            await self._safe_websocket_send(stream_output)

            logfire.info("Task completed successfully")
            return [json.loads(json.dumps(asdict(i), cls=DateTimeEncoder)) for i in self.orchestrator_response]
        
        except Exception as e:
            error_msg = f"Critical orchestration error: {str(e)}\n{traceback.format_exc()}"
            logfire.error(error_msg)
            
            if stream_output:
                stream_output.output = error_msg
                stream_output.status_code = 500
                self.orchestrator_response.append(stream_output)
                await self._safe_websocket_send(stream_output)
            
            # Even in case of critical error, return what we have
            try:
                return [json.loads(json.dumps(asdict(i), cls=DateTimeEncoder)) for i in self.orchestrator_response]
            except Exception as serialize_error:
                logfire.error(f"Failed to serialize response: {str(serialize_error)}")
                # Last resort - return a simple error message
                return [{"error": error_msg, "status_code": 500}]

        finally:
            logfire.info("Orchestration process complete")
            # Clear any sensitive data

    async def shutdown(self):
        """Clean shutdown of orchestrator"""
        try:
            # Close websocket if open
            if self.websocket:
                await self.websocket.close()
            
            # Clear all responses
            self.orchestrator_response = []
            
            logfire.info("Orchestrator shutdown complete")
            
        except Exception as e:
            logfire.error(f"Error during shutdown: {str(e)}")
            raise