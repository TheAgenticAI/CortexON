"""
Tracing Decorators

Provides decorators for automatically tracing agent tools and functions.
Minimal overhead when tracing is disabled.
"""

import functools
import inspect
from typing import Any, Callable, Optional, TypeVar, Union

from .config import is_tracing_enabled
from .steps import trace_step

F = TypeVar('F', bound=Callable[..., Any])


def trace_agent_tool(
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator to automatically trace agent tool execution.
    
    Usage:
        @trace_agent_tool(agent_name="MyAgent", tool_name="my_tool")
        async def my_tool_function(ctx, param1, param2):
            # Tool logic here
            return result
    
    Args:
        agent_name: Name of the agent (can be inferred from context)
        tool_name: Name of the tool (defaults to function name)
        
    Returns:
        Decorated function with automatic tracing
    """
    def decorator(func: F) -> F:
        if not is_tracing_enabled():
            # If tracing is disabled, return function unchanged for zero overhead
            return func
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Try to infer agent name from context if not provided
            inferred_agent = agent_name
            if inferred_agent is None and args:
                # Look for RunContext with agent info
                ctx = args[0]
                if hasattr(ctx, 'deps') and hasattr(ctx.deps, 'stream_output'):
                    stream_output = ctx.deps.stream_output
                    if hasattr(stream_output, 'agent_name'):
                        inferred_agent = stream_output.agent_name
            
            # Use function name as tool name if not specified
            actual_tool_name = tool_name or func.__name__
            
            async with trace_step(inferred_agent or "Unknown", actual_tool_name):
                return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't use the async context manager
            # So we'll use start_step/end_step manually
            from .steps import start_step, end_step
            
            inferred_agent = agent_name
            if inferred_agent is None and args:
                ctx = args[0]
                if hasattr(ctx, 'deps') and hasattr(ctx.deps, 'stream_output'):
                    stream_output = ctx.deps.stream_output
                    if hasattr(stream_output, 'agent_name'):
                        inferred_agent = stream_output.agent_name
            
            actual_tool_name = tool_name or func.__name__
            
            start_step(inferred_agent or "Unknown", actual_tool_name)
            try:
                result = func(*args, **kwargs)
                end_step("success")
                return result
            except Exception as e:
                end_step("error", e)
                raise
        
        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def trace_function(
    name: Optional[str] = None,
    agent_name: str = "System"
) -> Callable[[F], F]:
    """
    Decorator to trace any function as a system operation.
    
    Usage:
        @trace_function(name="data_processing", agent_name="DataProcessor")
        def process_data(data):
            # Processing logic
            return processed_data
    
    Args:
        name: Name for the traced operation (defaults to function name)
        agent_name: Agent name to use for tracing
        
    Returns:
        Decorated function with automatic tracing
    """
    return trace_agent_tool(agent_name=agent_name, tool_name=name)


