#Standard library imports
import uuid
import threading
import os
from typing import List, Optional, Dict, Any, Union, Tuple
import json
from dataclasses import asdict

#Third party imports
from mcp.server.fastmcp import FastMCP
from fastapi import WebSocket
import logfire

#Local imports
from utils.stream_response_format import StreamResponse
# from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from agents.web_surfer import WebSurfer

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
    
    # async def plan_task(task: str) -> str:
    #     """Plans the task and assigns it to the appropriate agents"""
    #     try:
    #         logfire.info(f"Planning task: {task}")
    #         planner_stream_output = StreamResponse(
    #             agent_name="Planner Agent",
    #             instructions=task,
    #             steps=[],
    #             output="",
    #             status_code=0,
    #             message_id=str(uuid.uuid4())
    #         )
            
    #         await _safe_websocket_send(websocket, planner_stream_output)
            
    #         # Update planner stream
    #         planner_stream_output.steps.append("Planning task...")
    #         await _safe_websocket_send(websocket, planner_stream_output)
            
    #         # Run planner agent
    #         planner_response = await planner_agent.run(user_prompt=task)
            
    #         # Update planner stream with results
    #         plan_text = planner_response.data.plan
    #         planner_stream_output.steps.append("Task planned successfully")
    #         planner_stream_output.output = plan_text
    #         planner_stream_output.status_code = 200
    #         await _safe_websocket_send(websocket, planner_stream_output)
            
    #         return f"Task planned successfully\nTask: {plan_text}"
    #     except Exception as e:
    #         error_msg = f"Error planning task: {str(e)}"
    #         logfire.error(error_msg, exc_info=True)
            
    #         # Update planner stream with error
    #         if 'planner_stream_output' in locals():
    #             planner_stream_output.steps.append(f"Planning failed: {str(e)}")
    #             planner_stream_output.status_code = 500
    #             await _safe_websocket_send(websocket, planner_stream_output)
                
    #         return f"Failed to plan task: {error_msg}"
    
    async def code_task(task: str) -> str:
        """Assigns coding tasks to the coder agent"""
        try:
            logfire.info(f"Assigning coding task: {task}")
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
    
    # async def planner_agent_update(completed_task: str) -> str:
    #     """
    #     Updates the todo.md file to mark a task as completed and returns the full updated plan.
    #     """
    #     try:
    #         logfire.info(f"Updating plan with completed task: {completed_task}")
    #         # Create a new StreamResponse for Planner Agent update
    #         planner_stream_output = StreamResponse(
    #             agent_name="Planner Agent",
    #             instructions=f"Update todo.md to mark as completed: {completed_task}",
    #             steps=[],
    #             output="",
    #             status_code=0,
    #             message_id=str(uuid.uuid4())
    #         )
            
    #         # Send initial update
    #         await _safe_websocket_send(websocket, planner_stream_output)
            
    #         # Directly read and update the todo.md file
    #         base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    #         planner_dir = os.path.join(base_dir, "agents", "planner")
    #         todo_path = os.path.join(planner_dir, "todo.md")
            
    #         planner_stream_output.steps.append("Reading current todo.md...")
    #         await _safe_websocket_send(websocket, planner_stream_output)
            
    #         # Make sure the directory exists
    #         os.makedirs(planner_dir, exist_ok=True)
            
    #         try:
    #             # Check if todo.md exists
    #             if not os.path.exists(todo_path):
    #                 planner_stream_output.steps.append("No todo.md file found. Will create new one after task completion.")
    #                 await _safe_websocket_send(websocket, planner_stream_output)
                    
    #                 # We'll directly call planner_agent.run() to create a new plan first
    #                 plan_prompt = f"Create a simple task plan based on this completed task: {completed_task}"
    #                 plan_response = await planner_agent.run(user_prompt=plan_prompt)
    #                 current_content = plan_response.data.plan
    #             else:
    #                 # Read existing todo.md
    #                 with open(todo_path, "r") as file:
    #                     current_content = file.read()
    #                     planner_stream_output.steps.append(f"Found existing todo.md ({len(current_content)} bytes)")
    #                     await _safe_websocket_send(websocket, planner_stream_output)
                
    #             # Now call planner_agent.run() with specific instructions to update the plan
    #             update_prompt = f"""
    #             Here is the current todo.md content:
                
    #             {current_content}
                
    #             Please update this plan to mark the following task as completed: {completed_task}
    #             Return ONLY the fully updated plan with appropriate tasks marked as [x] instead of [ ].
    #             """
                
    #             planner_stream_output.steps.append("Asking planner to update the plan...")
    #             await _safe_websocket_send(websocket, planner_stream_output)
                
    #             updated_plan_response = await planner_agent.run(user_prompt=update_prompt)
    #             updated_plan = updated_plan_response.data.plan
                
    #             # Write the updated plan back to todo.md
    #             with open(todo_path, "w") as file:
    #                 file.write(updated_plan)
                
    #             planner_stream_output.steps.append("Plan updated successfully")
    #             planner_stream_output.output = updated_plan
    #             planner_stream_output.status_code = 200
    #             await _safe_websocket_send(websocket, planner_stream_output)
                
    #             return updated_plan
                
    #         except Exception as e:
    #             error_msg = f"Error during plan update operations: {str(e)}"
    #             logfire.error(error_msg, exc_info=True)
                
    #             planner_stream_output.steps.append(f"Plan update failed: {str(e)}")
    #             planner_stream_output.status_code = 500
    #             await _safe_websocket_send(websocket, planner_stream_output)
                
    #             return f"Failed to update the plan: {error_msg}"
            
    #     except Exception as e:
    #         error_msg = f"Error updating plan: {str(e)}"
    #         logfire.error(error_msg, exc_info=True)
            
    #         return f"Failed to update plan: {error_msg}"
    
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
        # "plan_task": (plan_task, "Plans the task and assigns it to the appropriate agents"),
        "code_task": (code_task, "Assigns coding tasks to the coder agent"),
        "web_surf_task": (web_surf_task, "Assigns web surfing tasks to the web surfer agent"),
        # "planner_agent_update": (planner_agent_update, "Updates the todo.md file to mark a task as completed")
    }
    
    # Register each tool with the specified server instance
    for name, (fn, desc) in tool_definitions.items():
        server_instance._tool_manager.add_tool(fn, name=name, description=desc)
    
    logfire.info(f"Successfully registered {len(tool_definitions)} tools with the MCP server on port {port or server_manager.default_port}")
    

def get_unique_tool_name(tool_name: str, registered_names: set) -> str:
    """Ensure a tool name is unique by adding a suffix if necessary"""
    if tool_name not in registered_names:
        return tool_name
    
    # Add numeric suffix to make the name unique
    base_name = tool_name
    suffix = 1
    while f"{base_name}_{suffix}" in registered_names:
        suffix += 1
    return f"{base_name}_{suffix}"

def check_mcp_server_tools(server, registered_tools: set) -> None:
    """Check and fix duplicate tool names in an MCP server"""
    try:
        # This relies on implementation details of MCP Server
        if hasattr(server, '_mcp_api') and server._mcp_api:
            api = server._mcp_api
            
            # Check if API has a tool manager
            if hasattr(api, '_tool_manager'):
                tool_manager = api._tool_manager
                
                # Check if the tool manager has tools
                if hasattr(tool_manager, '_tools') and tool_manager._tools:
                    # Get a copy of original tool names
                    original_tools = list(tool_manager._tools.keys())
                    for tool_name in original_tools:
                        # If this tool name conflicts with existing ones
                        if tool_name in registered_tools:
                            # Create a unique name
                            unique_name = get_unique_tool_name(tool_name, registered_tools)
                            # Get the tool
                            tool = tool_manager._tools[tool_name]
                            # Add it with the new name
                            tool_manager._tools[unique_name] = tool
                            # Remove the old one
                            del tool_manager._tools[tool_name]
                            # Add the new name to the registry
                            registered_tools.add(unique_name)
                            logfire.info(f"Renamed tool {tool_name} to {unique_name} to avoid duplicate")
                        else:
                            # Add the name to the registry
                            registered_tools.add(tool_name)
    except Exception as e:
        logfire.error(f"Error checking MCP server tools: {str(e)}")