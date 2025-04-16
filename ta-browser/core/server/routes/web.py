import asyncio
from fastapi import APIRouter, HTTPException, WebSocket
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import time
from datetime import datetime
from queue import Empty
import os

from core.server.models.web import StreamRequestModel, StreamResponseModel
from core.server.constants import GLOBAL_TIMEOUT
from core.server.utils.timeout import timeout
from core.server.utils.session_tracker import SessionTracker
from core.utils.logger import Logger
from core.utils.init_client import initialize_client

logger = Logger()

router = APIRouter(prefix="/web")

async def stream_session_updates(
    session_id: str,
    session_tracker: SessionTracker
) -> AsyncGenerator[str, None]:
    """Stream updates for a specific session"""
    logger.debug(f"Starting streaming updates for session {session_id}")
    session_context = session_tracker.active_sessions[session_id]
    notification_queue = session_context["notification_queue"]
    orchestrator = session_context["orchestrator"]
    message_count = 0
    
    try:
        # Wait for browser initialization
        logger.debug("Waiting for browser initialization")
        await orchestrator.browser_initialized.wait()
        logger.info("Browser initialization confirmed")

        # Send initial metadata
        initial_data = StreamResponseModel(
            type="meta",
            message="Stream initialized. Session has started.",
            session_id=session_id,
            live_url=orchestrator.bb_live_url,
            metadata={
                "start_time": session_context["start_time"].isoformat(),
                "command": session_context.get("command", ""),
            }
        )
        yield f"data: {initial_data.model_dump_json()}\n\n"

        while session_id in session_tracker.active_sessions:
            try:
                notification = notification_queue.get_nowait()
                message_count += 1
                logger.debug(f"Processing notification #{message_count} for session {session_id}")

                # Build response
                response = StreamResponseModel(
                    type=notification.get("type", "info"),
                    message=notification.get("message", ""),
                    session_id=session_id,
                    metadata={
                        "step_count": notification.get("step_count", 0),
                        "processing_time": (datetime.utcnow() - session_context["start_time"]).total_seconds()
                    }
                )

                yield f"data: {response.model_dump_json()}\n\n"
                await asyncio.sleep(0.3)

                # Handle final states
                if notification.get("type") in ["final", "error"]:                                        
                    # Send final status update
                    final_response = StreamResponseModel(
                        type="status",
                        message=f"Session completed",
                        session_id=session_id,
                        metadata={
                            "step_count": notification.get("step_count", 0),
                            "processing_time": (datetime.utcnow() - session_context["start_time"]).total_seconds()
                        }
                    )
                    yield f"data: {final_response.model_dump_json()}\n\n"
                    break

            except Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing notification: {str(e)}")
                yield f"""data: {json.dumps({
                    'type': 'error',
                    'message': 'Stream processing failed',
                    'session_id': session_id,
                })}\n\n"""
                break

    except asyncio.CancelledError:
        logger.info(f"Stream cancelled for session {session_id}")
        process_task = session_context.get("process_task")
        if process_task and not process_task.done():
            process_task.cancel()
            try:
                await process_task  # Wait for cancellation
            except asyncio.CancelledError:
                pass

@router.post("/stream")
@timeout(GLOBAL_TIMEOUT)
async def stream_session(
    request: StreamRequestModel,
) -> StreamingResponse:
    """
    Stream a browser automation session based on the user's command.
    
    This endpoint accepts a command and URL, initializes a browser session,
    and streams back real-time updates as the command is executed.
    """
    print(f"[{time.time()}] Stream route: Starting processing")
    print(f"[STREAM] Received request with model_preference: {request.model_preference}")
    
    session_tracker = SessionTracker()

    try:
        # Generate a unique session ID
        session_id = str(time.time_ns())
        
        # Initialize the session
        logger.debug(f"Initializing stream session with ID {session_id}")
        print(f"[STREAM] Initializing session with model_preference: {request.model_preference}")
        session_info = await session_tracker.initialize_session(
            request.url, 
            request.critique_disabled, 
            session_id,
            request.model_preference
        )
        
        session_context = session_tracker.active_sessions.get(session_id)
        session_context["include_screenshot"] = False
        
        # Start the orchestrator
        logger.debug("Starting Orchestrator....")
        orchestrator = session_context["orchestrator"]
        process_task = asyncio.create_task(orchestrator.run(request.cmd))
        session_context["process_task"] = process_task

        # Return the streaming response
        return StreamingResponse(
            stream_session_updates(session_id, session_tracker),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error in /stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/model/preference")
async def get_model_preference():
    """Get the current model preference"""
    try:
        # Get model preference from environment or use default
        model_preference = os.getenv("MODEL_PREFERENCE", "Anthropic")
        return {"model_preference": model_preference}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))