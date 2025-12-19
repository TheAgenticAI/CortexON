"""
Step Lifecycle Management

Provides helper functions for managing agent action and tool execution steps.
Each step gets a unique step_id and proper context management.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from .context import TraceContext, get_current_trace, set_trace_context, ensure_run_context
from .logging import log


def start_step(agent_name: str, tool_name: Optional[str] = None) -> Optional[TraceContext]:
    """
    Start a new step within the current run.
    
    Args:
        agent_name: Name of the agent executing this step
        tool_name: Optional name of the tool being executed
        
    Returns:
        New step context, or None if tracing is disabled
    """
    if not _is_tracing_enabled():
        return None
    
    # Ensure we have a run context
    current_run = ensure_run_context()
    
    # Create new step context
    step_context = current_run.new_step(agent_name=agent_name, tool_name=tool_name)
    set_trace_context(step_context)
    
    # Log step start
    log.info(
        "Step started",
        agent_name=agent_name,
        tool_name=tool_name,
        step_id=step_context.step_id
    )
    
    return step_context


def end_step(status: str = "success", error: Optional[Exception] = None) -> None:
    """
    End the current step.
    
    Args:
        status: Status of the step completion ("success", "error", "cancelled")
        error: Optional exception if step failed
    """
    if not _is_tracing_enabled():
        return
    
    current_trace = get_current_trace()
    if current_trace is None or current_trace.step_id is None:
        return
    
    # Log step completion
    if error:
        log.error(
            "Step failed",
            status=status,
            error=str(error),
            error_type=type(error).__name__,
            step_id=current_trace.step_id,
            agent_name=current_trace.agent_name,
            tool_name=current_trace.tool_name
        )
    else:
        log.info(
            "Step completed",
            status=status,
            step_id=current_trace.step_id,
            agent_name=current_trace.agent_name,
            tool_name=current_trace.tool_name
        )
    
    # Reset to run-level context (remove step_id)
    run_context = TraceContext(run_id=current_trace.run_id)
    set_trace_context(run_context)


@asynccontextmanager
async def trace_step(
    agent_name: str, 
    tool_name: Optional[str] = None
) -> AsyncGenerator[Optional[TraceContext], None]:
    """
    Context manager for automatic step lifecycle management.
    
    Usage:
        async with trace_step("MyAgent", "my_tool") as step_context:
            # Your agent/tool logic here
            pass
    
    Args:
        agent_name: Name of the agent executing this step
        tool_name: Optional name of the tool being executed
        
    Yields:
        Step context, or None if tracing is disabled
    """
    step_context = start_step(agent_name, tool_name)
    
    try:
        yield step_context
        end_step("success")
    except Exception as e:
        end_step("error", e)
        raise


def _is_tracing_enabled() -> bool:
    """Check if tracing is enabled via environment variable."""
    return os.getenv("TRACING_ENABLED", "true").lower() == "true"



