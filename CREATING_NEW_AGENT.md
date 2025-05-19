# Creating a New Agent in CortexON

This guide explains how to create and integrate a new agent into the CortexON system.

## 1. Agent Structure

Each agent in CortexON follows a common pattern:

- **Agent definition** using the `pydantic_ai` framework
- **System prompt** that defines the agent's capabilities
- **Dependencies** for passing context between components
- **Tools** that define the agent's functionality

## 2. Step-by-Step Process

### Step 1: Create a New Agent File

Create a Python file in the `cortex_on/agents/` directory:

```python
# cortex_on/agents/my_new_agent.py

# Standard library imports
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Third-party imports
import logfire
from fastapi import WebSocket
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel

# Local application imports
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse

# Define dependencies class
@dataclass
class MyNewAgentDeps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None

# Define system prompt
my_new_agent_system_prompt = """You are a specialized agent in the CortexON system designed to [DESCRIBE SPECIFIC PURPOSE].

Your capabilities include:
1. [CAPABILITY 1]
2. [CAPABILITY 2]
3. [CAPABILITY 3]

You will receive tasks from the Orchestrator and should respond with detailed results.

[INCLUDE ANY SPECIFIC GUIDELINES OR REQUIREMENTS]
"""

# Initialize the model
model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    anthropic_client=get_client()
)

# Create the agent
my_new_agent = Agent(
    model=model,
    name="My New Agent",
    system_prompt=my_new_agent_system_prompt,
    deps_type=MyNewAgentDeps
)

# Define agent tools
@my_new_agent.tool
async def perform_task(ctx: RunContext[MyNewAgentDeps], task_description: str) -> str:
    """Perform the main task for this agent"""
    try:
        logfire.info(f"My New Agent performing task: {task_description}")
        
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Starting task...")
            if ctx.deps.websocket:
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Implement your agent's core functionality here
        # ...
        
        result = f"Task completed successfully: {task_description}"
        
        # Update stream output
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Task completed")
            ctx.deps.stream_output.output = result
            ctx.deps.stream_output.status_code = 200
            if ctx.deps.websocket:
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return result
    except Exception as e:
        error_msg = f"Error in My New Agent: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Task failed: {str(e)}")
            ctx.deps.stream_output.status_code = 500
            if ctx.deps.websocket:
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return error_msg

# Helper function for sending WebSocket messages
async def _safe_websocket_send(websocket: Optional[WebSocket], message: Any) -> bool:
    """Safely send message through websocket with error handling"""
    try:
        if websocket and websocket.client_state.CONNECTED:
            from dataclasses import asdict
            import json
            await websocket.send_text(json.dumps(asdict(message)))
            logfire.debug("WebSocket message sent")
            return True
        return False
    except Exception as e:
        logfire.error(f"WebSocket send failed: {str(e)}")
        return False
```

### Step 2: Update the Orchestrator Agent

Modify `cortex_on/agents/orchestrator_agent.py` to include your new agent:

1. Import your new agent:
```python
from agents.my_new_agent import my_new_agent, MyNewAgentDeps
```

2. Add a new tool to the orchestrator_agent:
```python
@orchestrator_agent.tool
async def my_new_agent_task(ctx: RunContext[orchestrator_deps], task: str) -> str:
    """Assigns tasks to the new agent"""
    try:
        logfire.info(f"Assigning task to My New Agent: {task}")
        
        # Create a new StreamResponse for the agent
        new_agent_stream_output = StreamResponse(
            agent_name="My New Agent",
            instructions=task,
            steps=[],
            output="",
            status_code=0
        )
        
        # Add to orchestrator's response collection if available
        if ctx.deps.agent_responses is not None:
            ctx.deps.agent_responses.append(new_agent_stream_output)
        
        # Send initial update
        await _safe_websocket_send(ctx.deps.websocket, new_agent_stream_output)
        
        # Create deps with the new stream_output
        deps_for_new_agent = MyNewAgentDeps(
            websocket=ctx.deps.websocket,
            stream_output=new_agent_stream_output
        )
        
        # Run the agent
        agent_response = await my_new_agent.run(
            user_prompt=task,
            deps=deps_for_new_agent
        )
        
        # Extract response data
        response_data = agent_response.data.content
        
        # Update stream_output with results
        new_agent_stream_output.output = response_data
        new_agent_stream_output.status_code = 200
        new_agent_stream_output.steps.append("Task completed successfully")
        await _safe_websocket_send(ctx.deps.websocket, new_agent_stream_output)
        
        # Add a reminder in the result message to update the plan
        response_with_reminder = f"{response_data}\n\nReminder: You must now call planner_agent_update with the completed task description: \"{task} (my_new_agent)\""
        
        return response_with_reminder
    except Exception as e:
        error_msg = f"Error assigning task to My New Agent: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream_output with error
        new_agent_stream_output.steps.append(f"Task failed: {str(e)}")
        new_agent_stream_output.status_code = 500
        await _safe_websocket_send(ctx.deps.websocket, new_agent_stream_output)
        
        return f"Failed to assign task to My New Agent: {error_msg}"
```

3. Update the orchestrator's system prompt to include your new agent:

```python
orchestrator_system_prompt = """You are an AI orchestrator that manages a team of agents to solve tasks...

[AGENT CAPABILITIES]
1. web_surfer_agent:
   - Handles authentication and credential tasks
   - Browses and extracts web information and interacts with web pages
   
2. coder_agent:
   - Implements technical solutions
   - Executes code operations

3. my_new_agent:
   - [DESCRIBE YOUR AGENT'S CAPABILITIES]
   - [LIST KEY FUNCTIONS]

[AVAILABLE TOOLS]
...
5. my_new_agent_task(task: str) -> str:
   - Assigns tasks to the my_new_agent
   - Handles [DESCRIBE WHAT YOUR AGENT HANDLES]
   - Returns [DESCRIBE WHAT YOUR AGENT RETURNS]
   - Updates UI with progress and results
...
```

### Step 3: Update the Instructor

In `cortex_on/instructor.py`, import your new agent:

```python
# Local application imports
from agents.code_agent import coder_agent
from agents.orchestrator_agent import orchestrator_agent, orchestrator_deps
from agents.planner_agent import planner_agent
from agents.web_surfer import WebSurfer
from agents.my_new_agent import my_new_agent  # Add this line
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
```

### Step 4: Update the Planner Agent (Optional)

The Planner Agent is responsible for creating task plans and determining which specialized agent should handle each task. To fully integrate your new agent, you need to update the planner to recognize and utilize your agent's capabilities.

#### 4.1 Update the Agents List

In `cortex_on/agents/planner_agent.py`, add your new agent to the agents list:

```python
# Find this line near the top of the file
agents = ["coder_agent", "web_surfer_agent"]

# Update it to include your new agent
agents = ["coder_agent", "web_surfer_agent", "my_new_agent"]
```

#### 4.2 Add Agent Capabilities to the System Prompt

Find the `<critical>` section in the planner prompt and add your agent's capabilities:

```python
# Locate this section in planner_prompt
<critical>
    AGENT CAPABILITIES [IMMUTABLE]:
    
    web_surfer_agent PRIMARY FUNCTIONS:
    1. AUTHORIZED credential access
    2. AUTOMATED login execution
    3. SECURE vault integration
    4. FULL authentication rights
    5. COMPLETE account access
    
    coder_agent functions:
    1. Code execution
    2. Technical implementation
    
    # Add your new agent's capabilities
    my_new_agent functions:
    1. [SPECIFIC CAPABILITY 1]
    2. [SPECIFIC CAPABILITY 2]
    3. [SPECIFIC CAPABILITY 3]
```

#### 4.3 Testing and Validation

After updating the Planner Agent, test that it correctly assigns tasks to your new agent by:

1. Creating a new plan that would logically require your agent's capabilities
2. Verifying that the planner assigns appropriate tasks to your agent
3. Ensuring the format includes your agent name in parentheses at the end of tasks

#### 4.4 Example Plan Format with Your New Agent

The resulting plan created by the Planner Agent should include tasks for your new agent in this format:

```
# Task Plan

## 1. Data Gathering
- [ ] Search for relevant information (web_surfer_agent)
- [ ] Extract key data points (web_surfer_agent)

## 2. Analysis
- [ ] Process and analyze the data (my_new_agent)
- [ ] Generate visualization of results (my_new_agent)

## 3. Implementation
- [ ] Create code implementation (coder_agent)
- [ ] Test and validate results (coder_agent)
```

This ensures that the Orchestrator will delegate tasks to your new agent when executing the plan.

## 3. Agent Best Practices

1. **Error Handling**: Always wrap agent functionality in try-except blocks and provide meaningful error messages
2. **Progress Updates**: Regularly update the stream_output with steps to provide real-time feedback
3. **Logging**: Use logfire for consistent logging
4. **Idempotency**: Ensure agent operations are idempotent where possible
5. **Resource Cleanup**: Always clean up resources in finally blocks
6. **WebSocket Communication**: Use the _safe_websocket_send helper for all WebSocket communication

## 4. Testing Your New Agent

1. Add test cases in the appropriate test files
2. Test the agent in isolation before integrating with the orchestrator
3. Test the full system integration to ensure proper coordination

## 5. Example Agent Types

Consider these types of specialized agents you might want to create:

1. **Data Analysis Agent**: For processing and analyzing datasets
2. **Document Processing Agent**: For handling PDFs, Word docs, and other document formats
3. **Image Analysis Agent**: For processing and analyzing images
4. **Audio Processing Agent**: For transcription and audio analysis
5. **API Integration Agent**: For connecting with specific external APIs

Each specialized agent should focus on a specific task domain to maintain clear separation of concerns.