"""
Tests for the tracing system.

Validates that tracing works correctly across async boundaries and integrates
properly with FastAPI and PydanticAI components.
"""

import asyncio
import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import tracing components
from tracing import (
    TraceContext, 
    get_current_trace, 
    set_trace_context,
    TracingMiddleware,
    start_step,
    end_step,
    trace_step,
    log as trace_log,
    trace_agent_tool
)
from tracing.config import TracingConfig, set_config


class TestTraceContext:
    """Test TraceContext functionality."""
    
    def test_new_run_creates_unique_ids(self):
        """Test that new_run creates unique run_ids."""
        ctx1 = TraceContext.new_run()
        ctx2 = TraceContext.new_run()
        
        assert ctx1.run_id != ctx2.run_id
        assert ctx1.step_id is None
        assert ctx1.agent_name is None
        assert ctx1.tool_name is None
    
    def test_new_step_preserves_run_id(self):
        """Test that new_step preserves run_id but creates new step_id."""
        run_ctx = TraceContext.new_run()
        step_ctx = run_ctx.new_step("TestAgent", "test_tool")
        
        assert step_ctx.run_id == run_ctx.run_id
        assert step_ctx.step_id is not None
        assert step_ctx.step_id != run_ctx.step_id
        assert step_ctx.agent_name == "TestAgent"
        assert step_ctx.tool_name == "test_tool"
    
    def test_to_dict(self):
        """Test TraceContext serialization."""
        ctx = TraceContext(
            run_id="test-run-123",
            step_id="test-step-456",
            agent_name="TestAgent",
            tool_name="test_tool"
        )
        
        expected = {
            "run_id": "test-run-123",
            "step_id": "test-step-456", 
            "agent_name": "TestAgent",
            "tool_name": "test_tool"
        }
        
        assert ctx.to_dict() == expected


class TestContextVars:
    """Test contextvars functionality."""
    
    def test_context_isolation(self):
        """Test that context is isolated between different contexts."""
        ctx1 = TraceContext.new_run()
        ctx2 = TraceContext.new_run()
        
        set_trace_context(ctx1)
        assert get_current_trace() == ctx1
        
        set_trace_context(ctx2)
        assert get_current_trace() == ctx2
        
        set_trace_context(None)
        assert get_current_trace() is None
    
    @pytest.mark.asyncio
    async def test_async_context_propagation(self):
        """Test that context propagates across async boundaries."""
        ctx = TraceContext.new_run()
        set_trace_context(ctx)
        
        async def inner_function():
            return get_current_trace()
        
        result = await inner_function()
        assert result == ctx


class TestTracingMiddleware:
    """Test FastAPI tracing middleware."""
    
    def test_middleware_adds_run_id_header(self):
        """Test that middleware adds X-Run-ID header to responses."""
        app = FastAPI()
        app.add_middleware(TracingMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Run-ID" in response.headers
        assert len(response.headers["X-Run-ID"]) > 0
    
    def test_middleware_disabled(self):
        """Test that middleware can be disabled."""
        app = FastAPI()
        app.add_middleware(TracingMiddleware, enabled=False)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Run-ID" not in response.headers
    
    def test_middleware_sets_context(self):
        """Test that middleware sets trace context."""
        app = FastAPI()
        app.add_middleware(TracingMiddleware)
        
        captured_context = None
        
        @app.get("/test")
        async def test_endpoint():
            nonlocal captured_context
            captured_context = get_current_trace()
            return {"message": "test"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert captured_context is not None
        assert captured_context.run_id == response.headers["X-Run-ID"]


class TestStepLifecycle:
    """Test step lifecycle management."""
    
    def setup_method(self):
        """Set up test environment."""
        # Enable tracing for tests
        config = TracingConfig(enabled=True, log_format="json")
        set_config(config)
        
        # Set up a run context
        self.run_ctx = TraceContext.new_run()
        set_trace_context(self.run_ctx)
    
    def test_start_step_creates_step_context(self):
        """Test that start_step creates proper step context."""
        step_ctx = start_step("TestAgent", "test_tool")
        
        assert step_ctx is not None
        assert step_ctx.run_id == self.run_ctx.run_id
        assert step_ctx.step_id is not None
        assert step_ctx.agent_name == "TestAgent"
        assert step_ctx.tool_name == "test_tool"
        
        # Context should be updated
        current = get_current_trace()
        assert current == step_ctx
    
    def test_end_step_resets_to_run_context(self):
        """Test that end_step resets to run-level context."""
        start_step("TestAgent", "test_tool")
        end_step("success")
        
        current = get_current_trace()
        assert current is not None
        assert current.run_id == self.run_ctx.run_id
        assert current.step_id is None  # Should be reset
    
    @pytest.mark.asyncio
    async def test_trace_step_context_manager(self):
        """Test the trace_step context manager."""
        async with trace_step("TestAgent", "test_tool") as step_ctx:
            assert step_ctx is not None
            assert step_ctx.agent_name == "TestAgent"
            assert step_ctx.tool_name == "test_tool"
            
            current = get_current_trace()
            assert current == step_ctx
        
        # After context manager, should be back to run context
        current = get_current_trace()
        assert current.step_id is None
    
    @pytest.mark.asyncio
    async def test_trace_step_handles_exceptions(self):
        """Test that trace_step properly handles exceptions."""
        with pytest.raises(ValueError):
            async with trace_step("TestAgent", "test_tool"):
                raise ValueError("Test error")
        
        # Should still reset context after exception
        current = get_current_trace()
        assert current.step_id is None


class TestTracedLogger:
    """Test structured logging functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        config = TracingConfig(enabled=True, log_format="json")
        set_config(config)
        
        self.run_ctx = TraceContext.new_run()
        set_trace_context(self.run_ctx)
    
    @patch('builtins.print')
    def test_logger_includes_trace_metadata(self, mock_print):
        """Test that logger includes trace metadata in logs."""
        step_ctx = start_step("TestAgent", "test_tool")
        
        trace_log.info("Test message", extra_field="extra_value")
        
        # Should have called print with JSON log
        assert mock_print.called
        log_output = mock_print.call_args[0][0]
        log_data = json.loads(log_output)
        
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["run_id"] == step_ctx.run_id
        assert log_data["step_id"] == step_ctx.step_id
        assert log_data["agent_name"] == "TestAgent"
        assert log_data["tool_name"] == "test_tool"
        assert log_data["extra_field"] == "extra_value"
    
    @patch('builtins.print')
    def test_logger_works_without_trace_context(self, mock_print):
        """Test that logger works when no trace context is set."""
        set_trace_context(None)
        
        trace_log.info("Test message")
        
        assert mock_print.called
        log_output = mock_print.call_args[0][0]
        log_data = json.loads(log_output)
        
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        # Should not have trace fields
        assert "run_id" not in log_data


class TestTraceAgentTool:
    """Test the trace_agent_tool decorator."""
    
    def setup_method(self):
        """Set up test environment."""
        config = TracingConfig(enabled=True, log_format="json")
        set_config(config)
        
        self.run_ctx = TraceContext.new_run()
        set_trace_context(self.run_ctx)
    
    @pytest.mark.asyncio
    async def test_decorator_traces_async_function(self):
        """Test that decorator properly traces async functions."""
        @trace_agent_tool(agent_name="TestAgent", tool_name="test_function")
        async def test_function(param1, param2):
            current = get_current_trace()
            assert current.agent_name == "TestAgent"
            assert current.tool_name == "test_function"
            return f"{param1}-{param2}"
        
        result = await test_function("hello", "world")
        assert result == "hello-world"
        
        # Should be back to run context
        current = get_current_trace()
        assert current.step_id is None
    
    def test_decorator_traces_sync_function(self):
        """Test that decorator properly traces sync functions."""
        @trace_agent_tool(agent_name="TestAgent", tool_name="test_function")
        def test_function(param1, param2):
            current = get_current_trace()
            assert current.agent_name == "TestAgent"
            assert current.tool_name == "test_function"
            return f"{param1}-{param2}"
        
        result = test_function("hello", "world")
        assert result == "hello-world"
        
        # Should be back to run context
        current = get_current_trace()
        assert current.step_id is None
    
    @pytest.mark.asyncio
    async def test_decorator_handles_exceptions(self):
        """Test that decorator properly handles exceptions."""
        @trace_agent_tool(agent_name="TestAgent", tool_name="test_function")
        async def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await test_function()
        
        # Should still reset context
        current = get_current_trace()
        assert current.step_id is None


class TestIntegration:
    """Integration tests for the complete tracing system."""
    
    def test_end_to_end_tracing(self):
        """Test complete tracing flow from HTTP request to agent execution."""
        app = FastAPI()
        app.add_middleware(TracingMiddleware)
        
        captured_contexts = []
        
        @trace_agent_tool(agent_name="TestAgent", tool_name="process_request")
        async def process_request(data):
            captured_contexts.append(get_current_trace())
            return {"processed": data}
        
        @app.post("/process")
        async def process_endpoint(data: dict):
            captured_contexts.append(get_current_trace())
            result = await process_request(data["input"])
            return result
        
        client = TestClient(app)
        response = client.post("/process", json={"input": "test_data"})
        
        assert response.status_code == 200
        assert "X-Run-ID" in response.headers
        
        # Should have captured contexts at both levels
        assert len(captured_contexts) == 2
        
        # Both should have same run_id
        run_id = response.headers["X-Run-ID"]
        assert captured_contexts[0].run_id == run_id
        assert captured_contexts[1].run_id == run_id
        
        # First should be run-level, second should be step-level
        assert captured_contexts[0].step_id is None
        assert captured_contexts[1].step_id is not None
        assert captured_contexts[1].agent_name == "TestAgent"
        assert captured_contexts[1].tool_name == "process_request"


if __name__ == "__main__":
    pytest.main([__file__])


