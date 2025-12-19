# CortexON Tracing System

A lightweight execution tracing and structured logging system for multi-agent workflows. Provides unique `run_id` and `step_id` tracking across async boundaries with minimal overhead.

## Features

- **Unique Request Tracking**: Every user request gets a unique `run_id`
- **Step-Level Tracing**: Every agent action or tool execution gets a unique `step_id`
- **Async-Safe**: Uses `contextvars` for proper context propagation across async boundaries
- **Structured Logging**: JSON-friendly logs with automatic trace metadata injection
- **Logfire Integration**: Compatible with Pydantic Logfire for observability
- **Zero Overhead**: Can be disabled with near-zero performance impact
- **Non-Invasive**: Integrates cleanly without breaking existing APIs

## Quick Start

### 1. Enable Tracing

Set environment variables:

```bash
export TRACING_ENABLED=true
export LOG_FORMAT=json
```

### 2. Add Middleware

```python
from fastapi import FastAPI
from tracing import TracingMiddleware

app = FastAPI()
app.add_middleware(TracingMiddleware)
```

### 3. Use Structured Logging

```python
from tracing import log

# Logs automatically include run_id, step_id, agent_name, tool_name
log.info("Processing request", user_id=123, action="login")
```

### 4. Trace Agent Tools

```python
from tracing import trace_agent_tool

@trace_agent_tool(agent_name="MyAgent", tool_name="process_data")
async def process_data(data):
    log.info("Processing data", size=len(data))
    # Your logic here
    return processed_data
```

## Core Components

### TraceContext

Container for trace metadata that propagates across async calls:

```python
from tracing import TraceContext, set_trace_context

# Create new run context
run_ctx = TraceContext.new_run()
set_trace_context(run_ctx)

# Create step context
step_ctx = run_ctx.new_step("AgentName", "tool_name")
```

### Step Lifecycle

Manual step management:

```python
from tracing import start_step, end_step

# Start a step
step_ctx = start_step("MyAgent", "my_tool")

try:
    # Your logic here
    end_step("success")
except Exception as e:
    end_step("error", e)
```

Context manager (recommended):

```python
from tracing import trace_step

async with trace_step("MyAgent", "my_tool"):
    # Your logic here - automatic success/error handling
    pass
```

### Structured Logging

The `log` object automatically injects trace metadata:

```python
from tracing import log

# With active trace context, this produces:
# {
#   "level": "INFO",
#   "message": "Processing user request",
#   "run_id": "550e8400-e29b-41d4-a716-446655440000",
#   "step_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
#   "agent_name": "UserAgent",
#   "tool_name": "process_request",
#   "user_id": 123,
#   "action": "login"
# }
log.info("Processing user request", user_id=123, action="login")
```

### Decorators

Automatic tracing for functions:

```python
from tracing import trace_agent_tool

@trace_agent_tool(agent_name="DataProcessor", tool_name="validate_input")
async def validate_input(data):
    log.info("Validating input", schema="user_data")
    # Validation logic
    return is_valid
```

## Configuration

Environment variables:

- `TRACING_ENABLED`: Enable/disable tracing (default: `true`)
- `LOG_FORMAT`: Log format - `json` or `text` (default: `json`)
- `TRACING_INCLUDE_SENSITIVE`: Include sensitive data in traces (default: `false`)
- `TRACING_MAX_STEP_DEPTH`: Maximum step nesting depth (default: `10`)

Programmatic configuration:

```python
from tracing.config import TracingConfig, set_config

config = TracingConfig(
    enabled=True,
    log_format="json",
    include_sensitive=False,
    max_step_depth=10
)
set_config(config)
```

## Integration Examples

### FastAPI Endpoint

```python
from fastapi import FastAPI
from tracing import TracingMiddleware, trace_agent_tool, log

app = FastAPI()
app.add_middleware(TracingMiddleware)

@trace_agent_tool(agent_name="APIHandler", tool_name="process_request")
async def process_request(data):
    log.info("Processing API request", endpoint="/api/data")
    # Processing logic
    return result

@app.post("/api/data")
async def api_endpoint(data: dict):
    return await process_request(data)
```

### PydanticAI Agent Tool

```python
from pydantic_ai import Agent, RunContext
from tracing import trace_agent_tool, log

@agent.tool
@trace_agent_tool(agent_name="MyAgent", tool_name="search_database")
async def search_database(ctx: RunContext, query: str):
    log.info("Searching database", query=query)
    # Database search logic
    return results
```

### Multi-Agent Workflow

```python
from tracing import trace_step, log

async def orchestrate_workflow(task):
    log.info("Starting workflow", task=task)
    
    # Planning phase
    async with trace_step("Planner", "create_plan"):
        plan = await create_plan(task)
        log.info("Plan created", steps=len(plan.steps))
    
    # Execution phase
    for i, step in enumerate(plan.steps):
        async with trace_step("Executor", f"execute_step_{i}"):
            result = await execute_step(step)
            log.info("Step completed", step=i, result=result)
    
    log.info("Workflow completed")
```

## HTTP Headers

The middleware automatically adds trace information to HTTP responses:

- `X-Run-ID`: The unique run identifier for the request

## Best Practices

1. **Use Context Managers**: Prefer `trace_step()` over manual `start_step()`/`end_step()`
2. **Meaningful Names**: Use descriptive agent and tool names
3. **Structured Data**: Include relevant context in log calls
4. **Error Handling**: Let the tracing system handle errors automatically
5. **Performance**: Disable tracing in production if not needed

## Troubleshooting

### No Trace Metadata in Logs

- Check that `TRACING_ENABLED=true`
- Ensure trace context is set (middleware should handle this for HTTP requests)
- Verify you're using the tracing `log` object, not standard logging

### Context Not Propagating

- Ensure you're using `async`/`await` properly
- Check that context is set before calling traced functions
- Verify contextvars are working in your Python environment

### Performance Impact

- Disable tracing with `TRACING_ENABLED=false` for zero overhead
- Use `LOG_FORMAT=text` for slightly better performance than JSON
- Consider reducing `TRACING_MAX_STEP_DEPTH` for deeply nested workflows

## Examples

See `examples/tracing_demo.py` for a complete demonstration of all tracing features.

## Testing

Run the test suite:

```bash
cd cortex_on
python -m pytest tests/test_tracing.py -v
```

## Architecture

The tracing system consists of:

- **Context Management** (`context.py`): TraceContext and contextvars integration
- **Middleware** (`middleware.py`): FastAPI middleware for request-level tracing
- **Step Management** (`steps.py`): Step lifecycle and context managers
- **Structured Logging** (`logging.py`): Trace-aware logging with Logfire integration
- **Decorators** (`decorators.py`): Automatic tracing decorators
- **Configuration** (`config.py`): Environment-based configuration

The system is designed to be:
- **Lightweight**: Minimal overhead when enabled, zero when disabled
- **Non-invasive**: No changes to existing API contracts
- **Async-safe**: Proper context propagation across async boundaries
- **Observable**: Rich structured logging for debugging and monitoring



