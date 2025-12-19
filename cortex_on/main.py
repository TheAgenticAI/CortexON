# Standard library imports
from typing import List, Optional

# Third-party imports
from fastapi import FastAPI, WebSocket

# Local application imports
from instructor import SystemInstructor
from tracing import TracingMiddleware


app: FastAPI = FastAPI()

# Add tracing middleware
app.add_middleware(TracingMiddleware)

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
