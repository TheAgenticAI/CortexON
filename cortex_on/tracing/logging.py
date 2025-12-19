"""
Structured Logging with Trace Context

Provides a logging helper that automatically injects trace metadata into logs.
Compatible with Pydantic Logfire and falls back gracefully if tracing is disabled.
"""

import os
from typing import Any, Dict, Optional

try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False

from .context import get_current_trace


class TracedLogger:
    """
    Logger that automatically injects trace metadata into structured logs.
    
    Features:
    - Automatic run_id and step_id injection
    - Agent and tool name context
    - Logfire integration when available
    - Graceful fallback to standard logging
    - JSON-friendly structured output
    """
    
    def __init__(self):
        self.enabled = self._is_tracing_enabled()
        self.json_format = os.getenv("LOG_FORMAT", "json").lower() == "json"
    
    def _get_trace_metadata(self) -> Dict[str, Any]:
        """Extract current trace metadata for logging."""
        if not self.enabled:
            return {}
        
        trace = get_current_trace()
        if trace is None:
            return {}
        
        metadata = {"run_id": trace.run_id}
        
        if trace.step_id:
            metadata["step_id"] = trace.step_id
        if trace.agent_name:
            metadata["agent_name"] = trace.agent_name
        if trace.tool_name:
            metadata["tool_name"] = trace.tool_name
            
        return metadata
    
    def _log_with_context(self, level: str, message: str, **kwargs) -> None:
        """Internal logging method that adds trace context."""
        # Merge trace metadata with provided kwargs
        log_data = {**self._get_trace_metadata(), **kwargs}
        
        if LOGFIRE_AVAILABLE and hasattr(logfire, level.lower()):
            # Use Logfire if available
            log_func = getattr(logfire, level.lower())
            log_func(message, **log_data)
        else:
            # Fallback to print-based logging
            if self.json_format:
                import json
                log_entry = {
                    "level": level.upper(),
                    "message": message,
                    **log_data
                }
                print(json.dumps(log_entry))
            else:
                # Simple text format
                context_str = " ".join(f"{k}={v}" for k, v in log_data.items())
                print(f"[{level.upper()}] {message} {context_str}")
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with trace context."""
        self._log_with_context("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with trace context."""
        self._log_with_context("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with trace context."""
        self._log_with_context("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with trace context."""
        self._log_with_context("error", message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with trace context."""
        self._log_with_context("critical", message, **kwargs)
    
    @staticmethod
    def _is_tracing_enabled() -> bool:
        """Check if tracing is enabled via environment variable."""
        return os.getenv("TRACING_ENABLED", "true").lower() == "true"


# Global logger instance
log = TracedLogger()


def configure_tracing_logging(
    enabled: Optional[bool] = None,
    json_format: Optional[bool] = None
) -> None:
    """
    Configure the global traced logger.
    
    Args:
        enabled: Override tracing enabled state
        json_format: Override JSON format preference
    """
    global log
    
    if enabled is not None:
        log.enabled = enabled
    if json_format is not None:
        log.json_format = json_format



