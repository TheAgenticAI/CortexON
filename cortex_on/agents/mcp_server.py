from mcp.server.fastmcp import FastMCP
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.mcp import RunContext
from fastapi import WebSocket
import os
from typing import List, Optional, Dict, Any, Union, Tuple
import json
from dataclasses import asdict
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent
from agents.code_agent import coder_agent
from agents.code_agent import coder_agent, CoderAgentDeps
from agents.orchestrator_agent import orchestrator_deps
from agents.web_surfer import WebSurfer
import logfire

# Initialize the single MCP server
server = FastMCP("CortexON MCP Server", host="0.0.0.0", port=3001)


@server.tool()
async def plan_task(task: str, ctx: RunContext[orchestrator_deps]) -> str:
    """Plans the task and assigns it to the appropriate agents"""
    try:
        logfire.info(f"Planning task: {task} and context: {ctx}")
        print(f"Planning task: {task} and context: {ctx}")
        # Create a new StreamResponse for Planner Agent
        planner_stream_output = StreamResponse(
            agent_name="Planner Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )
        
        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(planner_stream_output)
            
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Update planner stream
        planner_stream_output.steps.append("Planning task...")
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Run planner agent
        planner_response = await planner_agent.run(user_prompt=task)
        
        # Update planner stream with results
        plan_text = planner_response.data.plan
        planner_stream_output.steps.append("Task planned successfully")
        planner_stream_output.output = plan_text
        planner_stream_output.status_code = 200
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Also update orchestrator stream
        ctx.deps.stream_output.steps.append("Task planned successfully")
        await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Task planned successfully\nTask: {plan_text}"
    except Exception as e:
        error_msg = f"Error planning task: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update planner stream with error
        if planner_stream_output:
            planner_stream_output.steps.append(f"Planning failed: {str(e)}")
            planner_stream_output.status_code = 500
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
        # Also update orchestrator stream
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Planning failed: {str(e)}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Failed to plan task: {error_msg}"


@server.tool()
async def code_task(task: str, ctx: RunContext[orchestrator_deps]) -> str:
    """Assigns coding tasks to the coder agent"""
    try:
        logfire.info(f"Assigning coding task: {task}")
        print(f"Assigning coding task: {task} and context: {ctx}")
        # Create a new StreamResponse for Coder Agent
        coder_stream_output = StreamResponse(
            agent_name="Coder Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(coder_stream_output)

        # Send initial update for Coder Agent
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        # Create deps with the new stream_output
        deps_for_coder_agent = CoderAgentDeps(
            websocket=ctx.deps.websocket,
            stream_output=coder_stream_output
        )

        # Run coder agent
        coder_response = await coder_agent.run(
            user_prompt=task,
            deps=deps_for_coder_agent
        )

        # Extract response data
        response_data = coder_response.data.content

        # Update coder_stream_output with coding results
        coder_stream_output.output = response_data
        coder_stream_output.status_code = 200
        coder_stream_output.steps.append("Coding task completed successfully")
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        # Add a reminder in the result message to update the plan using planner_agent_update
        response_with_reminder = f"{response_data}\n\nReminder: You must now call planner_agent_update with the completed task description: \"{task} (coder_agent)\""

        return response_with_reminder
    except Exception as e:
        error_msg = f"Error assigning coding task: {str(e)}"
        logfire.error(error_msg, exc_info=True)

        # Update coder_stream_output with error
        coder_stream_output.steps.append(f"Coding task failed: {str(e)}")
        coder_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)

        return f"Failed to assign coding task: {error_msg}"


@server.tool()
async def web_surf_task(task: str,ctx: RunContext[orchestrator_deps]) -> str:
    """Assigns web surfing tasks to the web surfer agent"""
    try:
        logfire.info(f"Assigning web surfing task: {task}")
        
        # Create a new StreamResponse for WebSurfer
        web_surfer_stream_output = StreamResponse(
            agent_name="Web Surfer",
            instructions=task,
            steps=[],
            output="",
            status_code=0,
            live_url=None
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(web_surfer_stream_output)

        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        
        # Initialize WebSurfer agent
        web_surfer_agent = WebSurfer(api_url="http://localhost:8000/api/v1/web/stream")
        
        # Run WebSurfer with its own stream_output
        success, message, messages = await web_surfer_agent.generate_reply(
            instruction=task,
            websocket=ctx.deps.websocket,
            stream_output=web_surfer_stream_output
        )
        
        # Update WebSurfer's stream_output with final result
        if success:
            web_surfer_stream_output.steps.append("Web search completed successfully")
            web_surfer_stream_output.output = message
            web_surfer_stream_output.status_code = 200

            # Add a reminder to update the plan
            message_with_reminder = f"{message}\n\nReminder: You must now call planner_agent_update with the completed task description: \"{task} (web_surfer_agent)\""
        else:
            web_surfer_stream_output.steps.append(f"Web search completed with issues: {message[:100]}")
            web_surfer_stream_output.status_code = 500
            message_with_reminder = message
        
        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        
        web_surfer_stream_output.steps.append(f"WebSurfer completed: {'Success' if success else 'Failed'}")
        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        
        return message_with_reminder
    except Exception as e:
        error_msg = f"Error assigning web surfing task: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update WebSurfer's stream_output with error
        web_surfer_stream_output.steps.append(f"Web search failed: {str(e)}")
        web_surfer_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
        return f"Failed to assign web surfing task: {error_msg}"

@server.tool()
async def ask_human(question: str, ctx: RunContext[orchestrator_deps]) -> str:
    """Sends a question to the frontend and waits for human input"""
    try:
        logfire.info(f"Asking human: {question}")
        print(f"Asking human: {question} and context: {ctx}")
        # Create a new StreamResponse for Human Input
        human_stream_output = StreamResponse(
            agent_name="Human Input",
            instructions=question,
            steps=[],
            output="",
            status_code=0
        )

        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(human_stream_output)

        # Send the question to frontend
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        # Update stream with waiting message
        human_stream_output.steps.append("Waiting for human input...")
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        # Wait for response from frontend
        response = await ctx.deps.websocket.receive_text()
        
        # Update stream with response
        human_stream_output.steps.append("Received human input")
        human_stream_output.output = response
        human_stream_output.status_code = 200
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        return response
    except Exception as e:
        error_msg = f"Error getting human input: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        human_stream_output.steps.append(f"Failed to get human input: {str(e)}")
        human_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, human_stream_output)
        
        return f"Failed to get human input: {error_msg}"

@server.tool()
async def planner_agent_update(completed_task: str,ctx: RunContext[orchestrator_deps]) -> str:
    """
    Updates the todo.md file to mark a task as completed and returns the full updated plan.
    
    Args:
        completed_task: Description of the completed task including which agent performed it
    
    Returns:
        The complete updated todo.md content with tasks marked as completed
    """
    try:
        logfire.info(f"Updating plan with completed task: {completed_task}")
        print(f"Updating plan with completed task: {completed_task} and context: {ctx}")
        # Create a new StreamResponse for Planner Agent update
        planner_stream_output = StreamResponse(
            agent_name="Planner Agent",
            instructions=f"Update todo.md to mark as completed: {completed_task}",
            steps=[],
            output="",
            status_code=0
        )
        
        # Send initial update
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Directly read and update the todo.md file
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        planner_dir = os.path.join(base_dir, "agents", "planner")
        todo_path = os.path.join(planner_dir, "todo.md")
        
        planner_stream_output.steps.append("Reading current todo.md...")
        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
        
        # Make sure the directory exists
        os.makedirs(planner_dir, exist_ok=True)
        
        try:
            # Check if todo.md exists
            if not os.path.exists(todo_path):
                planner_stream_output.steps.append("No todo.md file found. Will create new one after task completion.")
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                # We'll directly call planner_agent.run() to create a new plan first
                plan_prompt = f"Create a simple task plan based on this completed task: {completed_task}"
                plan_response = await planner_agent.run(user_prompt=plan_prompt)
                current_content = plan_response.data.plan
            else:
                # Read existing todo.md
                with open(todo_path, "r") as file:
                    current_content = file.read()
                    planner_stream_output.steps.append(f"Found existing todo.md ({len(current_content)} bytes)")
                    await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            # Now call planner_agent.run() with specific instructions to update the plan
            update_prompt = f"""
            Here is the current todo.md content:
            
            {current_content}
            
            Please update this plan to mark the following task as completed: {completed_task}
            Return ONLY the fully updated plan with appropriate tasks marked as [x] instead of [ ].
            """
            
            planner_stream_output.steps.append("Asking planner to update the plan...")
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            updated_plan_response = await planner_agent.run(user_prompt=update_prompt)
            updated_plan = updated_plan_response.data.plan
            
            # Write the updated plan back to todo.md
            with open(todo_path, "w") as file:
                file.write(updated_plan)
            
            planner_stream_output.steps.append("Plan updated successfully")
            planner_stream_output.output = updated_plan
            planner_stream_output.status_code = 200
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            # Update orchestrator stream
            if ctx.deps.stream_output:
                ctx.deps.stream_output.steps.append(f"Plan updated to mark task as completed: {completed_task}")
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
            return updated_plan
            
        except Exception as e:
            error_msg = f"Error during plan update operations: {str(e)}"
            logfire.error(error_msg, exc_info=True)
            
            planner_stream_output.steps.append(f"Plan update failed: {str(e)}")
            planner_stream_output.status_code = 500
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            return f"Failed to update the plan: {error_msg}"
        
    except Exception as e:
        error_msg = f"Error updating plan: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream output with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Failed to update plan: {str(e)}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Failed to update plan: {error_msg}"

async def _safe_websocket_send(websocket: Optional[WebSocket], message: Any) -> bool:
    """Safely send message through websocket with error handling"""
    try:
        if websocket and websocket.client_state.CONNECTED:
            await websocket.send_text(json.dumps(asdict(message)))
            logfire.debug("WebSocket message sent (_safe_websocket_send): {message}", message=message)
            return True
        return False
    except Exception as e:
        logfire.error(f"WebSocket send failed: {str(e)}")
        return False
        
def run_server():
    """Run the MCP server"""
    server.run(transport="sse")

if __name__ == "__main__":
    run_server()