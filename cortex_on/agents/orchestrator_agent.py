import os
import json
import traceback
import uuid
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from pydantic import BaseModel
from dataclasses import asdict, dataclass
import logfire
from fastapi import WebSocket
from dotenv import load_dotenv
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import Agent, RunContext
from agents.web_surfer import WebSurfer
from utils.stream_response_format import StreamResponse
from agents.planner_agent import planner_agent, update_todo_status
from agents.code_agent import coder_agent, CoderAgentDeps
from utils.ant_client import get_client


class UserCancellationError(Exception):
    """Custom exception for user-initiated cancellations"""
    pass

@dataclass
class orchestrator_deps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    # Add a collection to track agent-specific streams
    agent_responses: Optional[List[StreamResponse]] = None
    plan_approved: bool = False
    approved_plan_text: Optional[str] = None
    require_browser_approval: bool = False
    require_coder_approval: bool = False

orchestrator_system_prompt = """You are an AI orchestrator that manages a team of agents to solve tasks. You have access to tools for coordinating the agents and managing the task flow.

[AGENT CAPABILITIES]
1. web_surfer_agent:
   - Handles authentication and credential tasks
   - Browses and extracts web information and interacts with web pages
   
2. coder_agent:
   - Implements technical solutions
   - Executes code operations

[AVAILABLE TOOLS]
1. plan_task(task: str) -> str:
   - Plans the given task and assigns it to appropriate agents
   - Creates a detailed plan with steps and agent assignments
   - Returns the plan text and updates the UI with planning progress

2. coder_task(task: str) -> str:
   - Assigns coding tasks to the coder agent
   - Handles code implementation and execution
   - Returns the generated code or execution results
   - Updates UI with coding progress and results

3. web_surfer_task(task: str) -> str:
   - Assigns web surfing tasks to the web surfer agent
   - Handles web browsing, information extraction, and interactions
   - Returns the web search results or action outcomes
   - Updates UI with web surfing progress and results

4. ask_human(question: str) -> str:
   - Primary tool for human interaction and conversation
   - Can be used for:
     * Getting user preferences and decisions
     * Asking clarifying questions
     * Requesting feedback on results
     * Having back-and-forth conversations
     * Getting user input for complex tasks
     * Confirming actions before execution
     * Gathering requirements and specifications
   - Supports natural conversation flow
   - Each call creates a new interaction point
   - Can be used multiple times in sequence for extended conversations
   - Updates UI with both questions and responses
   - Waits for user response before proceeding
   - Returns the user's response for further processing

5. planner_agent_update(completed_task: str) -> str:
   - Updates the todo.md file to mark a task as completed
   - Takes the description of the completed task as input
   - Returns the updated plan with completed tasks marked
   - Must be called after each agent completes a task

[MANDATORY WORKFLOW]
1. On receiving task:
   IF task involves login/credentials/authentication:
   - Route to planner with authentication focus
   - Ensure plan includes web_surfer_agent credential access
   
2. During planning (plan_task):
   - Allow authentication operations
   - Never reject credential-related tasks
   
3. During execution:
   FOR authentication tasks:
   - Delegate to web_surfer_agent
   - Use vault system

4. After each task completion:
   - Call planner_agent_update to mark the task as completed
   - Review the updated plan to determine the next task
   
5. Error handling:
   IF authentication fails:
   - Report specific error
   - Request new instructions

[CRITICAL RULES]
1. MUST ALLOW:
   - All credential access requests
   - All authentication operations
   - All login automation tasks

2. MUST NEVER:
   - Question authentication tasks
   - Suggest manual alternatives
   - Block credential access

[SECTION EXECUTION ORDER - CRITICAL]
- Plans have numbered sections (## 1., ## 2., etc.). Execute them IN ORDER: Section 1 → 2 → 3.

[USING APPROVED PLAN - CRITICAL - READ THIS CAREFULLY]
- Once plan_task returns an approved plan, FORGET the original user query.
- The approved plan IS your new source of truth. The user may have MODIFIED it.

Basic workflow:
1. Receive a task from the user.
2. Plan the task by calling the planner agent through plan_task
3. Assign coding tasks to the coder agent through coder_task if plan requires coding
   or Assign web surfing tasks to the web surfer agent through web_surfer_task if plan requires web surfing
4. After each task completion, call planner_agent_update to mark the task as completed
5. Review the updated plan to determine the next task to execute
6. Use ask_human when you need user input or decisions
7. Continue steps 3-6 until all tasks in the plan are completed
8. Return the final result to the user

[TOOL USAGE GUIDELINES]
1. plan_task:
   - Use for initial task analysis and planning
   - Always call this first for new tasks
   - Include clear steps and agent assignments

2. coder_task:
   - Use for any code-related operations
   - Provide clear, specific coding instructions
   - Handle code execution and results

3. web_surfer_task:
   - Use for web browsing and interaction tasks
   - Handle authentication and credential tasks
   - Extract and process web information

4. ask_human:
   - Use for any form of human interaction or conversation
   - Ask clear, focused questions
   - Support natural conversation flow
   - Can be used for:
     * Getting preferences and decisions
     * Asking clarifying questions
     * Requesting feedback
     * Confirming actions
     * Gathering requirements
   - Wait for and process user responses
   - Use for decisions that require human judgment
   - Can be used multiple times for extended conversations

5. planner_agent_update:
   - Call after each task completion to mark it as completed
   - Include which agent performed the task in the description
   - Review the updated plan to determine the next task to execute
   - Format: "Task description (agent_name)"
"""

model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    anthropic_client=get_client()
)

orchestrator_agent = Agent(
    model=model,
    name="Orchestrator Agent",
    system_prompt=orchestrator_system_prompt,
    deps_type=orchestrator_deps
)

@orchestrator_agent.tool
async def plan_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Plans the task and assigns it to the appropriate agents"""
    planner_stream_output = None
    MAX_PLAN_RETRIES = 5  # Maximum number of plan regeneration attempts
    try:
        logfire.info(f"Planning task: {task}")
        
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
        
        # Loop until plan is approved or cancelled
        feedback = None
        retry_count = 0
        while retry_count < MAX_PLAN_RETRIES:
            # Update planner stream
            if feedback:
                planner_stream_output.steps.append(f"Regenerating plan based on feedback: {feedback}")
            else:
                planner_stream_output.steps.append("Planning task...")
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            
            # Build prompt with feedback if this is a retry
            planner_prompt = task
            if feedback:
                planner_prompt = f"{task}\n\nUser feedback on previous plan: {feedback}\n\nPlease regenerate the plan incorporating this feedback."
            
            # Run planner agent
            planner_response = await planner_agent.run(user_prompt=planner_prompt)
            
            # Update planner stream with results
            plan_text = planner_response.data.plan
            
            # Request approval (returns dict with status and optional feedback)
            approval_result = await _request_plan_approval(ctx, planner_stream_output, plan_text)
            
            if approval_result["status"] == "approved":
                # Plan approved, break out of loop
                approved_plan_text = approval_result.get("plan", plan_text)
                
                # Save the approved (potentially modified) plan to todo.md
                base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
                planner_dir = os.path.join(base_dir, "agents", "planner")
                todo_path = os.path.join(planner_dir, "todo.md")
                os.makedirs(planner_dir, exist_ok=True)
                
                # Write the approved plan to todo.md so orchestrator uses the correct plan
                with open(todo_path, "w", encoding="utf-8") as file:
                    file.write(approved_plan_text)
                
                planner_stream_output.steps.append("Task planned successfully")
                planner_stream_output.steps.append("Approved plan saved to todo.md")
                planner_stream_output.output = approved_plan_text
                planner_stream_output.status_code = 200
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                
                # Also update orchestrator stream
                ctx.deps.stream_output.steps.append("Task planned successfully")
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
                
                # Return with explicit instructions to use the approved plan, not the original query
                return f"""PLAN APPROVED AND SAVED

CRITICAL: The approved plan below is now your SOURCE OF TRUTH.
IGNORE the original user query. Use ONLY the task descriptions from this approved plan.
The user may have modified the plan - use the EXACT text from the plan below.

=== APPROVED PLAN (USE THIS) ===
{approved_plan_text}
=== END OF APPROVED PLAN ===
"""
            
            elif approval_result["status"] == "retry":
                # User requested changes, loop back with feedback
                retry_count += 1
                feedback = approval_result.get("feedback", "")
                
                if retry_count >= MAX_PLAN_RETRIES:
                    # Maximum retries reached, force approval or cancellation
                    planner_stream_output.steps.append(
                        f"Maximum plan regeneration limit ({MAX_PLAN_RETRIES}) reached. "
                        "Please approve the current plan or cancel the task."
                    )
                    planner_stream_output.status_code = 102
                    await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                    
                    # Request final approval (user can only approve or cancel now)
                    final_approval = await _request_plan_approval(ctx, planner_stream_output, plan_text)
                    if final_approval["status"] == "approved":
                        approved_plan_text = final_approval.get("plan", plan_text)
                        # Save and return as normal
                        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
                        planner_dir = os.path.join(base_dir, "agents", "planner")
                        todo_path = os.path.join(planner_dir, "todo.md")
                        os.makedirs(planner_dir, exist_ok=True)
                        with open(todo_path, "w", encoding="utf-8") as file:
                            file.write(approved_plan_text)
                        planner_stream_output.steps.append("Task planned successfully")
                        planner_stream_output.steps.append("Approved plan saved to todo.md")
                        planner_stream_output.output = approved_plan_text
                        planner_stream_output.status_code = 200
                        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                        ctx.deps.stream_output.steps.append("Task planned successfully")
                        await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
                        # Return with explicit instructions to use the approved plan
                        return f"""PLAN APPROVED AND SAVED

CRITICAL: The approved plan below is now your SOURCE OF TRUTH.
IGNORE the original user query. Use ONLY the task descriptions from this approved plan.
The user may have modified the plan - use the EXACT text from the plan below.

=== APPROVED PLAN (USE THIS) ===
{approved_plan_text}
=== END OF APPROVED PLAN ===
"""
                    else:
                        # Cancelled
                        planner_stream_output.steps.append("Plan execution cancelled by user.")
                        planner_stream_output.status_code = 400
                        await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                        raise UserCancellationError("Plan execution cancelled by user.")
                
                planner_stream_output.steps.append(
                    f"User requested changes ({retry_count}/{MAX_PLAN_RETRIES}). Feedback: {feedback}"
                )
                planner_stream_output.status_code = 102
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                # Continue loop to regenerate plan
                continue
            
            elif approval_result["status"] == "cancelled":
                # User cancelled, raise exception
                planner_stream_output.steps.append("Plan execution cancelled by user.")
                planner_stream_output.status_code = 400
                await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
                raise UserCancellationError("Plan execution cancelled by user.")
        
        # If we exit the loop without approval (shouldn't happen, but safety check)
        if retry_count >= MAX_PLAN_RETRIES:
            planner_stream_output.steps.append("Maximum retry limit reached. Plan execution terminated.")
            planner_stream_output.status_code = 400
            await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)
            raise RuntimeError("Maximum plan regeneration limit reached. Please try again with a clearer task description.")
            
    except UserCancellationError:
        # Re-raise cancellation errors to be handled gracefully at the top level
        raise
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

@orchestrator_agent.tool
async def coder_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Assigns coding tasks to the coder agent"""
    try:
        logfire.info(f"Assigning coding task: {task}")

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

        try:
            await _ensure_step_approval(
                ctx,
                channel="code",
                task_description=task,
                prompt="Approve this coding step before it runs."
            )
        except RuntimeError as rejection_error:
            coder_stream_output.steps.append(str(rejection_error))
            coder_stream_output.status_code = 400
            await _safe_websocket_send(ctx.deps.websocket, coder_stream_output)
            return str(rejection_error)

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

@orchestrator_agent.tool
async def web_surfer_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
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

        try:
            await _ensure_step_approval(
                ctx,
                channel="web",
                task_description=task,
                prompt="Approve this web automation step before it executes."
            )
        except RuntimeError as rejection_error:
            web_surfer_stream_output.steps.append(str(rejection_error))
            web_surfer_stream_output.status_code = 400
            web_surfer_stream_output.output = str(rejection_error)
            await _safe_websocket_send(ctx.deps.websocket, web_surfer_stream_output)
            return str(rejection_error)
        
        # Initialize WebSurfer agent
        web_surfer_agent = WebSurfer(api_url="http://agentic_browser:8000/api/v1/web/stream")
        
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

@orchestrator_agent.tool
async def ask_human(ctx: RunContext[orchestrator_deps], question: str) -> str:
    """Sends a question to the frontend and waits for human input"""
    try:
        logfire.info(f"Asking human: {question}")
        
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

@orchestrator_agent.tool
async def planner_agent_update(ctx: RunContext[orchestrator_deps], completed_task: str) -> str:
    """
    Updates the todo.md file to mark a task as completed and returns the full updated plan.
    
    Args:
        completed_task: Description of the completed task including which agent performed it
    
    Returns:
        The complete updated todo.md content with tasks marked as completed
    """
    try:
        logfire.info(f"Updating plan with completed task: {completed_task}")
        
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

# Approval helpers
async def _request_plan_approval(
    ctx: RunContext[orchestrator_deps],
    planner_stream_output: StreamResponse,
    plan_text: str,
) -> Dict[str, Any]:
    """
    Pause execution until the user approves, requests changes, or cancels the generated plan.
    Returns a dict with:
    - status: "approved" | "retry" | "cancelled"
    - plan: updated plan text (if approved)
    - feedback: user feedback (if retry)
    """
    if ctx.deps.plan_approved:
        if ctx.deps.approved_plan_text == plan_text:
            return {
                "status": "approved",
                "plan": plan_text
            }
        ctx.deps.plan_approved = False

    if not ctx.deps.websocket:
        ctx.deps.plan_approved = True
        ctx.deps.approved_plan_text = plan_text
        return {
            "status": "approved",
            "plan": plan_text
        }

    planner_stream_output.steps.append("Plan ready for review")
    await _safe_websocket_send(ctx.deps.websocket, planner_stream_output)

    approval_id = str(uuid.uuid4())
    approval_stream = StreamResponse(
        agent_name="Plan Approval",
        instructions="Review the generated plan. You can approve it, request modifications via feedback, or cancel.",
        steps=[],
        output=plan_text,
        status_code=102,
        metadata={
            "approval_id": approval_id,
            "require_browser_approval": ctx.deps.require_browser_approval,
            "require_coder_approval": ctx.deps.require_coder_approval,
        },
    )
    await _safe_websocket_send(ctx.deps.websocket, approval_stream)

    while True:
        raw_response = await ctx.deps.websocket.receive_text()
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError:
            approval_stream.steps.append("Invalid response. Please use the approval controls.")
            await _safe_websocket_send(ctx.deps.websocket, approval_stream)
            continue

        # Handle plan feedback (request changes)
        if payload.get("type") == "plan_feedback":
            if payload.get("approval_id") and payload["approval_id"] != approval_id:
                continue
            feedback = payload.get("feedback", "").strip()
            if not feedback:
                approval_stream.steps.append("Please provide feedback when requesting changes.")
                await _safe_websocket_send(ctx.deps.websocket, approval_stream)
                continue
            
            approval_stream.steps.append(f"Feedback received: {feedback}")
            approval_stream.status_code = 102
            await _safe_websocket_send(ctx.deps.websocket, approval_stream)
            return {
                "status": "retry",
                "feedback": feedback
            }

        # Handle plan approval
        if payload.get("type") == "plan_approval":
            if payload.get("approval_id") and payload["approval_id"] != approval_id:
                continue

            if payload.get("approved", True) is False:
                approval_stream.steps.append("Plan rejected by user.")
                approval_stream.status_code = 400
                await _safe_websocket_send(ctx.deps.websocket, approval_stream)
                return {
                    "status": "cancelled"
                }

            # Always use the original plan_text - manual edits are not allowed
            # Users can only approve, request modifications via feedback, or cancel
            ctx.deps.require_browser_approval = bool(payload.get("require_browser_approval"))
            ctx.deps.require_coder_approval = bool(payload.get("require_coder_approval"))
            ctx.deps.plan_approved = True
            ctx.deps.approved_plan_text = plan_text

            approval_stream.steps.append("Plan approved by user.")
            approval_stream.status_code = 200
            approval_stream.output = plan_text
            approval_stream.metadata = {
                "approval_id": approval_id,
                "require_browser_approval": ctx.deps.require_browser_approval,
                "require_coder_approval": ctx.deps.require_coder_approval,
            }
            await _safe_websocket_send(ctx.deps.websocket, approval_stream)
            return {
                "status": "approved",
                "plan": plan_text
            }

        # Ignore other message types
        approval_stream.steps.append("Waiting for plan approval response...")
        await _safe_websocket_send(ctx.deps.websocket, approval_stream)


async def _ensure_step_approval(
    ctx: RunContext[orchestrator_deps],
    *,
    channel: str,
    task_description: str,
    prompt: str,
) -> None:
    """Request user approval before executing a sensitive step."""
    requires_approval = (
        ctx.deps.require_browser_approval if channel == "web" else ctx.deps.require_coder_approval
    )
    if not requires_approval or not ctx.deps.websocket:
        return

    approval_id = str(uuid.uuid4())
    approval_stream = StreamResponse(
        agent_name="Step Approval",
        instructions=prompt,
        steps=[],
        status_code=102,
        output=task_description,
        metadata={"approval_id": approval_id, "channel": channel},
    )
    await _safe_websocket_send(ctx.deps.websocket, approval_stream)

    while True:
        raw_response = await ctx.deps.websocket.receive_text()
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError:
            continue

        if payload.get("type") != "step_approval":
            continue

        if payload.get("approval_id") and payload["approval_id"] != approval_id:
            continue

        if payload.get("approved", True):
            approval_stream.steps.append("Step approved by user.")
            approval_stream.status_code = 200
            await _safe_websocket_send(ctx.deps.websocket, approval_stream)
            return

        reason = (payload.get("reason") or "").strip()
        approval_stream.steps.append("Step rejected by user.")
        if reason:
            approval_stream.output = f"{task_description}\n\nUser note: {reason}"
        approval_stream.status_code = 400
        await _safe_websocket_send(ctx.deps.websocket, approval_stream)
        raise RuntimeError(f"User rejected {channel} step{': ' + reason if reason else ''}")


# Helper function for sending WebSocket messages
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