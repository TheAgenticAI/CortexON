from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException
from core.utils.logger import Logger
from queue import Queue
from core.orchestrator import Orchestrator

logger = Logger()

class SessionTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, 'initialized'):
            self.sessions: Dict[str, Dict[str, Any]] = {}
            self.active_sessions: Dict[str, Dict] = {}
            self.initialized = True
    
    def get_active_sessions_status(self) -> dict:
        """Get active sessions status summary"""
        return {
            "count": len(self.active_sessions),
            "sessions": list(self.active_sessions.keys())
        }

    async def initialize_session(self, start_url: str, no_crit: bool, session_id: str, model_preference: str = "Anthropic") -> Dict[str, Any]:
        """Initialize a new session context"""
        logger.debug(f"Starting session initialization with URL: {start_url}")
        print(f"[SESSION_TRACKER] Initializing session with model_preference: {model_preference}")
        logger.set_job_id(session_id)
        
        orchestrator = None

        try:
            orchestrator = Orchestrator(input_mode="API", no_crit=no_crit)
            print(f"[SESSION_TRACKER] Passing model_preference: {model_preference} to orchestrator.async_init")
            await orchestrator.async_init(job_id=session_id, start_url=start_url, model_preference=model_preference)
            logger.debug(f"Orchestrator async_init completed with params: job_id={session_id}, start_url={start_url}, model_preference={model_preference}")

            notification_queue = Queue()
            orchestrator.notification_queue = notification_queue
            logger.debug("Notification queue initialized")
   
            session_context = {
                "orchestrator": orchestrator,
                "notification_queue": notification_queue,
                "start_time": datetime.now(),
                "current_url": start_url,
                "include_screenshot": False,
                "model_preference": model_preference
            }
            
            self.add_active_session(session_id, session_context)
            self.update_session(session_id, "Session initialized.", "INFO")
            logger.debug(f"Session Context for session added to active_sessions")
        
            return {
                "session_id": session_id,
                "context": session_context
            }
            
        except Exception as e:
            logger.error(f"Error during session initialization: {str(e)}")
            try:
                if session_id:
                    logger.debug(f"Attempting cleanup for session {session_id}")
                    await self.cleanup_session(session_id)
                    
                # Additional cleanup if orchestrator was created but not added to active_sessions
                if orchestrator and not session_id:
                    logger.debug("Cleaning up orphaned orchestrator")
                    await orchestrator.cleanup()
                
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")
                
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize session: {str(e)}"
            )

    def get_active_session(self, session_id: str) -> Optional[Dict]:
        """Get active session context"""
        return self.active_sessions.get(session_id)

    def add_active_session(self, session_id: str, context: Dict):
        self.active_sessions[session_id] = context
        
    async def cleanup_session(self, session_id: str) -> None:
        """Clean up session resources"""
        logger.debug(f"Starting cleanup for session {session_id}")
        if session_id in self.active_sessions:
            session_context = self.active_sessions[session_id]
            try:
                orchestrator = session_context["orchestrator"]
                await orchestrator.cleanup()
                
                duration = datetime.now() - session_context["start_time"]
                logger.info(f"Session {session_id} completed in {duration}")
                
            except Exception as e:
                logger.error(f"Error during session cleanup: {str(e)}", exc_info=True)
            finally:
                del self.active_sessions[session_id]
                logger.debug(f"Session {session_id} removed from active sessions")

    def update_session(self, session_id: str, message: str, message_type: str, step_count: Optional[int] = None) -> None:
        """Update session status information"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'last_message': 'Session started',
                'last_message_type': 'INFO',
                'last_updated': datetime.now(),
                'step_count': 0
            }
        
        update_data = {
            'last_message': message,
            'last_message_type': message_type,
            'last_updated': datetime.now()
        }
        
        # Always update step_count if provided
        if step_count is not None:
            update_data['step_count'] = step_count
            
        self.sessions[session_id].update(update_data)

    async def verify_browser_manager(self, session_id: str) -> bool:
        """Verify that browser manager is properly initialized"""
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                logger.error(f"No active session found for session {session_id}")
                return False
                
            orchestrator = session.get("orchestrator")
            if not orchestrator:
                logger.error(f"No orchestrator found for session {session_id}")
                return False
                
            if not orchestrator.browser_manager:
                logger.error(f"No browser manager initialized for session {session_id}")
                return False
                
            # Verify we can actually get a page
            page = await orchestrator.browser_manager.get_current_page()
            if not page:
                logger.error(f"Could not get current page for session {session_id}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying browser manager: {str(e)}")
            return False