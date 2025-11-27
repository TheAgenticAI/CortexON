# Standard library imports
import json
from typing import List, Optional

# Third-party imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logfire

# Local application imports
from instructor import SystemInstructor


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
    try:
        while True:
            try:
                data = await websocket.receive_text()
                await generate_response(data, websocket)
            except WebSocketDisconnect:
                logfire.info("Client disconnected from WebSocket")
                break
            except Exception as e:
                logfire.error(f"Error processing WebSocket message: {str(e)}")
                # Try to send error to client if still connected
                try:
                    if websocket.client_state.CONNECTED:
                        await websocket.send_text(json.dumps({"error": str(e)}))
                except:
                    pass
                break
    except WebSocketDisconnect:
        logfire.info("WebSocket connection closed by client")
    except Exception as e:
        logfire.error(f"WebSocket endpoint error: {str(e)}")
    finally:
        try:
            if websocket.client_state.CONNECTED:
                await websocket.close()
        except:
            pass
