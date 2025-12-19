"""
Trace Context Management

Provides TraceContext object and contextvars-based propagation across async boundaries.
Each user request gets a unique run_id, and each agent action gets a unique step_id.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TraceContext:
    """
    Container for trace metadata that propagates across async calls.
    
    Attributes:
        run_id: Unique identifier for the entire user request
        step_id: Optional unique identifier for current agent action/tool execution
        agent_name: Optional name of the currently executing agent
        tool_name: Optional name of the currently executing tool
    """
    run_id: str
    step_id: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    
    @classmethod
    def new_run(cls) -> "TraceContext":
        """Create a new trace context for a user request."""
        return cls(run_id=str(uuid.uuid4()))
    
    def new_step(self, agent_name: str, tool_name: Optional[str] = None) -> "TraceContext":
        """Create a new step context within the current run."""
        return TraceContext(
            run_id=self.run_id,
            step_id=str(uuid.uuid4()),
            agent_name=agent_name,
            tool_name=tool_name
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name
        }


# ContextVar for async-safe trace propagation
_trace_context: ContextVar[Optional[TraceContext]] = ContextVar("trace_context", default=None)


def get_current_trace() -> Optional[TraceContext]:
    """Get the current trace context, if any."""
    return _trace_context.get()


def set_trace_context(context: Optional[TraceContext]) -> None:
    """Set the current trace context."""
    _trace_context.set(context)


def ensure_run_context() -> TraceContext:
    """
    Ensure we have a run context, creating one if necessary.
    
    This is a fallback for cases where tracing wasn't properly initialized.
    """
    current = get_current_trace()
    if current is None:
        current = TraceContext.new_run()
        set_trace_context(current)
    return current



