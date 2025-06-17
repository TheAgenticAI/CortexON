# Standard library imports
from typing import List, Optional
import json

# Third-party imports
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Local application imports
from instructor import SystemInstructor
from utils.models import MCPRequest, MCPServerConfig


app: FastAPI = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


async def generate_response(task: str, websocket: Optional[WebSocket] = None):
    orchestrator: SystemInstructor = SystemInstructor()
    return await orchestrator.run(task, websocket)


@app.get("/agent/chat")
async def agent_chat(task: str) -> List:
    final_agent_response = await generate_response(task)
    return final_agent_response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await generate_response(data, websocket)


@app.get("/agent/mcp/servers")
async def get_mcp_servers():
    with open("config/external_mcp_servers.json", "r") as f:
        servers = json.load(f)

    servers_list = []
    for server in servers:
        servers_list.append(
            {
                "name": server,
                "description": servers[server]["description"],
                "status": servers[server]["status"],
            }
        )
    return servers_list


@app.get("/agent/mcp/servers/{server_name}")
async def get_mcp_server(server_name: str):
    with open("config/external_mcp_servers.json", "r") as f:
        servers = json.load(f)

    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")

    config = (
        {
            "command": servers[server_name]["command"],
            "args": servers[server_name]["args"],
            # 'env': servers[server_name]['env']
        }
        if servers[server_name]["status"] == "enabled"
        else {}
    )

    return {
        "name": server_name,
        "status": servers[server_name]["status"],
        "description": servers[server_name]["description"],
        "config": config,
    }


@app.post("/agent/mcp/servers")
async def configure_mcp_server(mcp_request: MCPRequest):
    with open("config/external_mcp_servers.json", "r") as f:
        servers = json.load(f)

    if mcp_request.action == "enable":
        if mcp_request.server_name not in servers:
            raise HTTPException(status_code=404, detail="Server not found")

        if not mcp_request.server_secret:
            raise HTTPException(
                status_code=400,
                detail=f"Server secret is required to enable {mcp_request.server_name}",
            )

        if servers[mcp_request.server_name]["status"] == "enabled":
            raise HTTPException(
                status_code=400, detail=f"{mcp_request.server_name} is already enabled"
            )

        servers[mcp_request.server_name]["status"] = "enabled"
        server_secret_key = servers[mcp_request.server_name]["secret_key"]
        servers[mcp_request.server_name]["env"][
            server_secret_key
        ] = mcp_request.server_secret

    elif mcp_request.action == "disable":
        if mcp_request.server_name not in servers:
            raise HTTPException(status_code=404, detail="Server not found")

        if servers[mcp_request.server_name]["status"] == "disabled":
            raise HTTPException(
                status_code=400, detail=f"{mcp_request.server_name} is already disabled"
            )

        servers[mcp_request.server_name]["status"] = "disabled"
        servers[mcp_request.server_name]["env"] = {}

    with open("config/external_mcp_servers.json", "w") as f:
        json.dump(servers, f, indent=4)

    config = (
        {
            "command": servers[mcp_request.server_name]["command"],
            "args": servers[mcp_request.server_name]["args"],
        }
        if servers[mcp_request.server_name]["status"] == "enabled"
        else {}
    )

    return {
        "name": mcp_request.server_name,
        "status": servers[mcp_request.server_name]["status"],
        "description": servers[mcp_request.server_name]["description"],
        "config": config,
    }


@app.post("/agent/mcp/servers/add")
async def add_mcp_server(server_name: str, server_config: MCPServerConfig):
    """Add a new MCP server configuration"""
    with open("config/external_mcp_servers.json", "r") as f:
        servers = json.load(f)

    if server_name in servers:
        raise HTTPException(
            status_code=400, detail=f"Server {server_name} already exists"
        )

    # Check if API key is provided and valid
    if server_config.has_valid_api_key():
        server_config.status = "enabled"
    else:
        server_config.status = "disabled"
        # Clear any empty or invalid API key
        if server_config.secret_key in server_config.env:
            server_config.env[server_config.secret_key] = ""

    # Add the new server configuration
    servers[server_name] = server_config.dict()

    # Write back to the file
    with open("config/external_mcp_servers.json", "w") as f:
        json.dump(servers, f, indent=4)

    return {
        "name": server_name,
        "status": server_config.status,
        "description": server_config.description,
        "config": (
            {"command": server_config.command, "args": server_config.args}
            if server_config.status == "enabled"
            else {}
        ),
        "message": (
            "Server added and enabled"
            if server_config.status == "enabled"
            else "Server added but disabled (API key required)"
        ),
    }


@app.delete("/agent/mcp/servers/{server_name}")
async def delete_mcp_server(server_name: str):
    """Delete an MCP server configuration"""
    with open("config/external_mcp_servers.json", "r") as f:
        servers = json.load(f)

    if server_name not in servers:
        raise HTTPException(
            status_code=404, detail=f"Server {server_name} not found"
        )

    # Remove the server configuration
    deleted_server = servers.pop(server_name)

    # Write back to the file
    with open("config/external_mcp_servers.json", "w") as f:
        json.dump(servers, f, indent=4)

    return {
        "name": server_name,
        "message": f"Server {server_name} deleted successfully",
        "deleted_server": {
            "description": deleted_server["description"],
            "status": deleted_server["status"],
        },
    }
