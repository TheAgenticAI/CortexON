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
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.anthropic import AnthropicModel
from mcp.server.fastmcp import FastMCP
from pydantic_ai.mcp import MCPServerHTTP

# Local application imports
from agents.orchestrator_agent import orchestrator_agent, orchestrator_deps, orchestrator_system_prompt
from utils.stream_response_format import StreamResponse
from agents.mcp_server import start_mcp_server, register_tools_for_main_mcp_server, server_manager
from connect_to_external_server import server_provider
from prompts import time_server_prompt
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
            orchestrator_agent._mcp_servers = servers
            orchestrator_agent.system_prompt = orchestrator_system_prompt + "\n\n" + system_prompt
            logfire.info(f"Updated orchestrator agent with {len(servers)} MCP servers. Current MCP servers: {orchestrator_agent._mcp_servers}")

            # Configure orchestrator_agent to use all configured MCP servers
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