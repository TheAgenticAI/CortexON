"""
Tracing System Demo

Demonstrates the CortexON tracing system with examples of:
- Manual step management
- Decorator-based tracing
- Structured logging
- Context propagation
"""

import asyncio
import os
from typing import Optional

# Set up environment for demo
os.environ["TRACING_ENABLED"] = "true"
os.environ["LOG_FORMAT"] = "json"

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tracing import (
    TraceContext,
    set_trace_context,
    start_step,
    end_step,
    trace_step,
    trace_agent_tool,
    log
)


async def demo_manual_tracing():
    """Demonstrate manual step management."""
    print("\n=== Manual Tracing Demo ===")
    
    # Create a run context
    run_ctx = TraceContext.new_run()
    set_trace_context(run_ctx)
    
    log.info("Starting manual tracing demo", run_id=run_ctx.run_id)
    
    # Manual step management
    start_step("DemoAgent", "data_processing")
    log.info("Processing data", input_size=1000)
    
    # Simulate some work
    await asyncio.sleep(0.1)
    
    log.info("Data processing completed", output_size=500)
    end_step("success")
    
    log.info("Manual tracing demo completed")


async def demo_context_manager():
    """Demonstrate context manager-based tracing."""
    print("\n=== Context Manager Demo ===")
    
    run_ctx = TraceContext.new_run()
    set_trace_context(run_ctx)
    
    log.info("Starting context manager demo")
    
    async with trace_step("DemoAgent", "file_processing") as step_ctx:
        log.info("Processing file", filename="demo.txt")
        
        # Nested step
        async with trace_step("DemoAgent", "validation"):
            log.info("Validating file format")
            await asyncio.sleep(0.05)
            log.info("Validation passed")
        
        log.info("File processing completed")
    
    log.info("Context manager demo completed")


@trace_agent_tool(agent_name="DemoAgent", tool_name="calculate_result")
async def calculate_something(x: int, y: int) -> int:
    """Example function with decorator-based tracing."""
    log.info("Calculating result", x=x, y=y)
    
    # Simulate computation
    await asyncio.sleep(0.1)
    result = x * y + 42
    
    log.info("Calculation completed", result=result)
    return result


@trace_agent_tool(agent_name="DemoAgent", tool_name="process_batch")
async def process_batch(items: list) -> dict:
    """Example of processing multiple items with tracing."""
    log.info("Starting batch processing", item_count=len(items))
    
    results = []
    for i, item in enumerate(items):
        # Each item gets its own nested step
        async with trace_step("DemoAgent", f"process_item_{i}"):
            log.info("Processing item", item=item, index=i)
            processed = f"processed_{item}"
            results.append(processed)
    
    log.info("Batch processing completed", results_count=len(results))
    return {"results": results, "total": len(results)}


async def demo_decorator_tracing():
    """Demonstrate decorator-based tracing."""
    print("\n=== Decorator Tracing Demo ===")
    
    run_ctx = TraceContext.new_run()
    set_trace_context(run_ctx)
    
    log.info("Starting decorator demo")
    
    # Simple calculation
    result = await calculate_something(10, 5)
    log.info("Got calculation result", result=result)
    
    # Batch processing
    items = ["item1", "item2", "item3"]
    batch_result = await process_batch(items)
    log.info("Got batch result", batch_result=batch_result)
    
    log.info("Decorator demo completed")


async def demo_error_handling():
    """Demonstrate error handling in tracing."""
    print("\n=== Error Handling Demo ===")
    
    run_ctx = TraceContext.new_run()
    set_trace_context(run_ctx)
    
    log.info("Starting error handling demo")
    
    # Demonstrate error in context manager
    try:
        async with trace_step("DemoAgent", "failing_operation"):
            log.info("About to fail")
            raise ValueError("Simulated error")
    except ValueError as e:
        log.info("Caught expected error", error=str(e))
    
    # Demonstrate error in decorated function
    @trace_agent_tool(agent_name="DemoAgent", tool_name="failing_function")
    async def failing_function():
        log.info("This function will fail")
        raise RuntimeError("Another simulated error")
    
    try:
        await failing_function()
    except RuntimeError as e:
        log.info("Caught expected error from decorated function", error=str(e))
    
    log.info("Error handling demo completed")


async def main():
    """Run all tracing demos."""
    print("CortexON Tracing System Demo")
    print("=" * 40)
    
    await demo_manual_tracing()
    await demo_context_manager()
    await demo_decorator_tracing()
    await demo_error_handling()
    
    print("\n=== Demo Complete ===")
    print("Check the logs above to see trace metadata in action!")


if __name__ == "__main__":
    asyncio.run(main())


