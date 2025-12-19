"""
FastAPI Tracing Middleware

Automatically creates run_id for every HTTP request and adds X-Run-ID to response headers.
Integrates with contextvars for async-safe trace propagation.
"""

import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .context import TraceContext, set_trace_context


class TracingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that creates a unique run_id for every request.
    
    Features:
    - Generates unique run_id per request
    - Sets trace context for async propagation
    - Adds X-Run-ID header to responses
    - Can be disabled via TRACING_ENABLED environment variable
    """
    
    def __init__(self, app, enabled: bool = None):
        """
        Initialize tracing middleware.
        
        Args:
            app: FastAPI application instance
            enabled: Override for tracing enabled state (defaults to TRACING_ENABLED env var)
        """
        super().__init__(app)
        if enabled is None:
            enabled = os.getenv("TRACING_ENABLED", "true").lower() == "true"
        self.enabled = enabled
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response with tracing context.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response with X-Run-ID header added
        """
        if not self.enabled:
            # If tracing is disabled, pass through without modification
            return await call_next(request)
        
        # Create new trace context for this request
        trace_context = TraceContext.new_run()
        set_trace_context(trace_context)
        
        # Process the request
        response = await call_next(request)
        
        # Add run_id to response headers
        response.headers["X-Run-ID"] = trace_context.run_id
        
        return response



