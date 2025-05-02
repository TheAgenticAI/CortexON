from mcp.server.fastmcp import FastMCP
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import RunContext
from fastapi import WebSocket
import os
from typing import List, Optional, Dict, Any, Union, Tuple
import json
from dataclasses import asdict
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from agents.orchestrator_agent import orchestrator_deps
from agents.web_surfer import WebSurfer
import logfire

# Initialize the single MCP server
server = FastMCP("CortexON MCP Server", host="0.0.0.0", port=3001)

# Note: All tools are now dynamically registered in instructor.py
# This avoids the problem of websocket not being available when tools are defined

def run_server():
    """Run the MCP server"""
    server.run(transport="sse")

if __name__ == "__main__":
    run_server()