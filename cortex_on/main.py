# Standard library imports
from typing import List, Optional
from contextlib import asynccontextmanager

# Third-party imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect ,Depends
from fastapi.middleware.cors import CORSMiddleware
import logfire

# Configure Logfire
logfire.configure()

# Local application imports
from instructor import SystemInstructor

# Default model preference is Anthropic
MODEL_PREFERENCE = "Anthropic"

# Global instructor instance
instructor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set default model preference at startup
    app.state.model_preference = MODEL_PREFERENCE
    logfire.info(f"Setting default model preference to: {MODEL_PREFERENCE}")

    # Initialize the instructor
    global instructor
    instructor = SystemInstructor(model_preference=MODEL_PREFERENCE)
    print("[STARTUP] Instructor initialized")
    
    yield
    
    # # Cleanup
    # if instructor:
    #     await instructor.shutdown()


app: FastAPI = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

async def get_model_preference() -> str:
    """
    Get the current model preference from app state
    """
    logfire.info(f"Current model preference: {app.state.model_preference}")
    return app.state.model_preference

@app.get("/set_model_preference")
async def set_model_preference(model: str):
    """
    Set the model preference (Anthropic or OpenAI) and reinitialize the instructor
    """
    if model not in ["Anthropic", "OpenAI"]:
        logfire.error(f"Invalid model preference attempted: {model}")
        return {"error": "Model must be 'Anthropic' or 'OpenAI'"}
    
    logfire.info(f"Changing model preference from {app.state.model_preference} to {model}")
    app.state.model_preference = model
    
    # Reinitialize the instructor with new model preference
    global instructor
    if instructor:
        await instructor.shutdown()
    instructor = SystemInstructor(model_preference=model)
    logfire.info(f"Instructor reinitialized with model preference: {model}")
    
    return {"message": f"Model preference set to {model}"}

async def generate_response(task: str, websocket: Optional[WebSocket] = None, model_preference: str = None):
    if model_preference is None:
        model_preference = app.state.model_preference
    logfire.info(f"Using model preference: {model_preference} for task: {task[:30]}...")
    
    global instructor
    if not instructor:
        instructor = SystemInstructor(model_preference=model_preference)
    
    return await instructor.run(task, websocket)

@app.get("/agent/chat")
async def agent_chat(task: str, model_preference: str = Depends(get_model_preference)) -> List:
    logfire.info(f"Received chat request with model preference: {model_preference}")
    final_agent_response = await generate_response(task, model_preference=model_preference)
    return final_agent_response

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    model_preference = app.state.model_preference
    logfire.info(f"New connection using model preference: {model_preference}")
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logfire.info(f"Received message, using model: {model_preference}")
                await generate_response(data, websocket, model_preference)
            except WebSocketDisconnect:
                print("[WEBSOCKET] Client disconnected")
                break
            except Exception as e:
                print(f"[WEBSOCKET] Error handling message: {str(e)}")
                if "disconnect message has been received" in str(e):
                    print(f"[WEBSOCKET] DIsconnect detected, closing connection: {str(e)}")
                    break
    except Exception as e:
        print(f"[WEBSOCKET] Connection error: {str(e)}")
        # finally:
        #     print("[WEBSOCKET] connection closed")
