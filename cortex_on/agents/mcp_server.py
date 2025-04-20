from mcp.server.fastmcp import FastMCP
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
import os
from utils.ant_client import get_client
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent
from agents.web_surfer import WebSurfer
import logfire

# Initialize the single MCP server
server = FastMCP("CortexON MCP Server", host="0.0.0.0", port=3001)


@server.tool()
async def plan_task(task: str) -> str:
    """Planner agent tool for creating task plans"""
    try:
        logfire.info(f"Planning task: {task}")
        planner_response = await planner_agent.run(user_prompt=task)
        return planner_response.data.plan
    except Exception as e:
        logfire.error(f"Error in planner: {str(e)}", exc_info=True)
        return f"Error in planner: {str(e)}"


@server.tool()
async def code_task(task: str) -> str:
    """Coder agent tool for implementing technical solutions"""
    try:
        logfire.info(f"Executing code task: {task}")
        coder_response = await coder_agent.run(user_prompt=task)
        return coder_response.data.content
    except Exception as e:
        logfire.error(f"Error in coder: {str(e)}", exc_info=True)
        return f"Error in coder: {str(e)}"


@server.tool()
async def web_surf_task(task: str) -> str:
    """Web surfer agent tool for web interactions"""
    try:
        logfire.info(f"Executing web surf task: {task}")
        web_surfer = WebSurfer(api_url="http://localhost:8000/api/v1/web/stream")
        success, message, _ = await web_surfer.generate_reply(
            instruction=task, websocket=None, stream_output=None
        )
        return message if success else f"Error in web surfer: {message}"
    except Exception as e:
        logfire.error(f"Error in web surfer: {str(e)}", exc_info=True)
        return f"Error in web surfer: {str(e)}"


def run_server():
    """Run the MCP server"""
    server.run(transport="sse")


if __name__ == "__main__":
    run_server()
