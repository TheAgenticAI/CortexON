# Standard library imports
from typing import List, Optional
import json

# Third-party imports
from fastapi import FastAPI, WebSocket, HTTPException

# Local application imports
from instructor import SystemInstructor
from utils.models import MCPRequest


app: FastAPI = FastAPI()

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
        servers =  json.load(f)
    
    servers_list = []
    for server in servers:
        servers_list.append({
            "name": server,
            "description": servers[server]["description"],
            "status": servers[server]["status"]
        })
    return servers_list

@app.get("/agent/mcp/servers/{server_name}")
async def get_mcp_server(server_name: str):
    with open("config/external_mcp_servers.json", "r") as f:
        servers =  json.load(f)
    
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    config = {
            'command': servers[server_name]['command'],
            'args': servers[server_name]['args']
            # 'env': servers[server_name]['env']
    } if servers[server_name]['status'] == 'enabled' else {}
    
    return {
        'name': server_name,
        'status': servers[server_name]['status'],
        'description': servers[server_name]['description'],
        'config': config
    }

@app.post("/agent/mcp/servers")
async def configure_mcp_server(mcp_request: MCPRequest):
    with open("config/external_mcp_servers.json", "r") as f:
        servers =  json.load(f)
    
    if mcp_request.server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if not mcp_request.server_secret:
        raise HTTPException(status_code=400, detail=f"Server secret is required to enable {mcp_request.server_name}")
    
    if mcp_request.action == 'enable':
        if servers[mcp_request.server_name]['status'] == 'enabled':
            raise HTTPException(status_code=400, detail=f"{mcp_request.server_name} is already enabled")
        servers[mcp_request.server_name]['status'] = 'enabled'
        server_secret_key = servers[mcp_request.server_name]['secret_key']
        servers[mcp_request.server_name]['env'][server_secret_key] = mcp_request.server_secret
    
    elif mcp_request.action == 'disable':
        if servers[mcp_request.server_name]['status'] == 'disabled':
            raise HTTPException(status_code=400, detail=f"{mcp_request.server_name} is already disabled")
        servers[mcp_request.server_name]['status'] = 'disabled'
        servers[mcp_request.server_name]['env'] = {}
        
    
    with open("config/external_mcp_servers.json", "w") as f:
        json.dump(servers, f, indent=4)
    
    config = {
            'command': servers[mcp_request.server_name]['command'],
            'args': servers[mcp_request.server_name]['args']
            # 'env': servers[server_name]['env']
    } if servers[mcp_request.server_name]['status'] == 'enabled' else {}
    
    return {
        'name': mcp_request.server_name,
        'status': servers[mcp_request.server_name]['status'],
        'description': servers[mcp_request.server_name]['description'],
        'config': config
    } 
    
