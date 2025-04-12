from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from core.main import orchestrator

router = APIRouter()

class ModelRequest(BaseModel):
    command: str
    parameters: Optional[Dict[str, Any]] = None

@router.post("/model/{model_id}")
async def handle_model_request(model_id: int, request: ModelRequest):
    """Handle POST requests to /model/{model_id}"""
    try:
        # Use the global orchestrator instance
        result = await orchestrator.handle_request(
            command=request.command,
            parameters=request.parameters or {}
        )
        
        return {"status": "success", "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 