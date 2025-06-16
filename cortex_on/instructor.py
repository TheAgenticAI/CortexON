# Standard library imports
import json
import os
import traceback
import yaml
import subprocess
import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

# Third-party imports
from dotenv import load_dotenv
from fastapi import WebSocket
import logfire
from pydantic import BaseModel

# Local application imports
from agents.orchestrator_agent import orchestrator_agent, orchestrator_deps, orchestrator_system_prompt
from utils.stream_response_format import StreamResponse
from agents.mcp_server import start_mcp_server, register_tools_for_main_mcp_server, server_manager, check_mcp_server_tools
from connect_to_external_server import server_provider
load_dotenv()

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

# Main Orchestrator Class
class SystemInstructor:
    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.stream_output: Optional[StreamResponse] = None
        self.orchestrator_response: List[StreamResponse] = []
        self.external_servers: Dict[str, Dict[str, Any]] = {}
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
    async def send_server_status_update(self, stream_output: StreamResponse, server_name: str, status: Dict[str, Any]) -> bool:
        """Send server status update via WebSocket
        
        Args:
            stream_output: The StreamResponse object to update
            server_name: Name of the server being accessed
            status: Status information to stream
        """
        try:
            # Ensure we have a server_status dictionary
            if not hasattr(stream_output, 'server_status') or stream_output.server_status is None:
                stream_output.server_status = {}
            
            # Add a timestamp to the status update
            status_with_timestamp = {**status, "timestamp": datetime.now().isoformat()}
            
            # Update the status in the stream_output
            stream_output.server_status[server_name] = status_with_timestamp
            
            # Add a step message for non-npx servers or if it's an important status
            important_statuses = ["ready", "error", "failed", "connected"]
            if server_name != 'npx' or status.get('status', '') in important_statuses:
                stream_output.steps.append(f"Server update from {server_name}: {status.get('status', 'processing')}")
            
            # Make sure the WebSocket is still connected
            if self.websocket and self.websocket.client_state.CONNECTED:
                # Send the update and retry if needed
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Try to send the message
                        await self.websocket.send_text(json.dumps(asdict(stream_output)))
                        logfire.debug(f"Server status update sent for {server_name}: {status.get('status')}")
                        return True
                    except Exception as send_err:
                        if attempt < max_retries - 1:
                            # Brief wait before retry
                            await asyncio.sleep(0.1 * (attempt + 1))
                            logfire.warning(f"Retrying server status update ({attempt+1}/{max_retries})")
                        else:
                            # Last attempt failed
                            logfire.error(f"Failed to send server status update after {max_retries} attempts: {str(send_err)}")
                            return False
            else:
                logfire.warning(f"WebSocket disconnected, couldn't send status update for {server_name}")
                return False
                
        except Exception as e:
            logfire.error(f"Failed to send server status update: {str(e)}")
            return False
        
    def _reset_orchestrator_agent(self):
        """Reset the orchestrator agent for a new chat session"""
        try:
            # Keep only the main server (first one) and remove all external servers
            if len(orchestrator_agent._mcp_servers) > 1:
                main_server = orchestrator_agent._mcp_servers[0]
                orchestrator_agent._mcp_servers = [main_server]
                logfire.info("Reset orchestrator_agent MCP servers to just the main server")
            
            # Reset the system prompt to its original state
            orchestrator_agent.system_prompt = orchestrator_system_prompt
            logfire.info("Reset orchestrator_agent system prompt to default")
            
            # If there's a tools manager, clear any cache it might have
            for server in orchestrator_agent._mcp_servers:
                if hasattr(server, '_mcp_api') and server._mcp_api:
                    api = server._mcp_api
                    if hasattr(api, '_tool_manager'):
                        tool_manager = api._tool_manager
                        if hasattr(tool_manager, '_cached_tool_schemas'):
                            tool_manager._cached_tool_schemas = None
                            logfire.info(f"Cleared tool schema cache for server {server}")
        except Exception as e:
            logfire.error(f"Error resetting orchestrator agent: {str(e)}")

    async def run(self, task: str, websocket: WebSocket, server_config: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """
        Main orchestration loop with comprehensive error handling
        
        Args:
            task: The task instructions
            websocket: The active WebSocket connection
            server_config: Optional configuration for MCP servers {name: port}
        """
        # Reset the orchestrator agent to ensure we start fresh for each new chat
        # self._reset_orchestrator_agent()
        
        self.websocket = websocket
        stream_output = StreamResponse(
            agent_name="Orchestrator",
            instructions=task,
            steps=[],
            output="",
            status_code=0,
            message_id=str(uuid.uuid4())
        )
        self.orchestrator_response = [stream_output]  # Reset the response list for new chat
        
        # Create dependencies with list to track agent responses
        deps_for_orchestrator = orchestrator_deps(
            websocket=self.websocket,
            stream_output=stream_output,
            agent_responses=self.orchestrator_response
        )

        try:
            # Initialize system
            await self._safe_websocket_send(stream_output)
            
            # Use the default port for main MCP server
            main_port = server_manager.default_port  # This is 8002
            
            # Merge default and external server configurations
            if server_config is None:
                server_config = {
                    "main": main_port
                }
            
            # Start the main MCP server - already handled by the framework
            start_mcp_server(port=main_port, name="main")
            register_tools_for_main_mcp_server(websocket=self.websocket, port=main_port)
            
            # Start each configured external MCP server
            servers, system_prompt = await server_provider.load_servers()
            
            # Send status update for each server being loaded
            for i, server in enumerate(servers):
                server_name = server.command.split('/')[-1] if hasattr(server, 'command') else f"server_{i}"
                await self.send_server_status_update(
                    stream_output,
                    server_name, 
                    {"status": "initializing", "progress": i/len(servers)*100}
                )
            
            # We need to make sure each MCP server has unique tool names
            # First, check the main MCP server's tools
            registered_tools = set()
            main_server = orchestrator_agent._mcp_servers[0]
            check_mcp_server_tools(main_server, registered_tools)
            
            # Now add each external server and check its tools
            for server in servers:
                # Check and deduplicate tools before adding
                check_mcp_server_tools(server, registered_tools)
                # Adding one at a time after checking
                orchestrator_agent._mcp_servers.append(server)
                logfire.info(f"Added MCP server: {server.__class__.__name__}")
            
            # Properly integrate external server capabilities into the system prompt
            updated_system_prompt = orchestrator_system_prompt
            if system_prompt and system_prompt.strip():
                if "[AVAILABLE TOOLS]" in updated_system_prompt:
                    sections = updated_system_prompt.split("[AVAILABLE TOOLS]")
                    updated_system_prompt = sections[0] + system_prompt + "\n\n[AVAILABLE TOOLS]" + sections[1]
                else:
                    # If we can't find the section, just append to the end (fallback)
                    updated_system_prompt = updated_system_prompt + "\n\n" + system_prompt
            
            orchestrator_agent.system_prompt = updated_system_prompt
            logfire.info(f"Updated orchestrator agent with {len(servers)} MCP servers. Current MCP servers: {orchestrator_agent._mcp_servers}")
            # Configure orchestrator_agent to use all configured MCP servers
            logfire.info("Starting to register MCP server tools with Claude")
            
            # Send another status update before starting MCP servers
            for i, server in enumerate(servers):
                server_name = server.command.split('/')[-1] if hasattr(server, 'command') else f"server_{i}"
                await self.send_server_status_update(
                    stream_output,
                    server_name, 
                    {"status": "connecting", "progress": 50 + i/len(servers)*25}
                )
                await asyncio.sleep(0.1)  # Brief pause to allow updates to be sent
            
            async with orchestrator_agent.run_mcp_servers():
                # Send status update that servers are ready
                for i, server in enumerate(servers):
                    server_name = server.command.split('/')[-1] if hasattr(server, 'command') else f"server_{i}"
                    await self.send_server_status_update(
                        stream_output,
                        server_name, 
                        {"status": "ready", "progress": 100}
                    )
                    await asyncio.sleep(0.1)  # Brief pause to allow updates to be sent
                    
                    # Start monitoring this server's status in the background
                    asyncio.create_task(
                        server_provider.monitor_server_status(
                            server_name,
                            lambda s, status: self.send_server_status_update(stream_output, s, status)
                        )
                    )
                                
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
            if "WebSocketDisconnect" in str(e):
                logfire.info("WebSocket disconnected. Client likely closed the connection.")
                try:
                    await self.shutdown()
                except Exception as shutdown_err:
                    logfire.error(f"Error during cleanup after disconnect: {shutdown_err}")
                return [json.loads(json.dumps(asdict(i), cls=DateTimeEncoder)) for i in self.orchestrator_response]
            
            error_msg = f"Critical orchestration error: {str(e)}\n{traceback.format_exc()}"
            logfire.error(error_msg)
            
            if stream_output:
                stream_output.output = error_msg
                stream_output.status_code = 500
                self.orchestrator_response.append(stream_output)
                await self._safe_websocket_send(stream_output)
            
            try:
                return [json.loads(json.dumps(asdict(i), cls=DateTimeEncoder)) for i in self.orchestrator_response]
            except Exception as serialize_error:
                logfire.error(f"Failed to serialize response: {str(serialize_error)}")
                # Last resort - return a simple error message
                return [{"error": error_msg, "status_code": 500}]

        finally:
            logfire.info("Orchestration process complete")

    async def shutdown(self):
        """Clean shutdown of orchestrator"""
        try:
            # Reset the orchestrator agent
            self._reset_orchestrator_agent()
            
            # Shut down all external MCP servers
            await server_provider.shutdown_servers()
            
            # Close websocket if open
            if self.websocket:
                await self.websocket.close()
            
            # Clear all responses
            self.orchestrator_response = []
            
            logfire.info("Orchestrator shutdown complete")
            
        except Exception as e:
            logfire.error(f"Error during shutdown: {str(e)}")
            raise