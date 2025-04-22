# Standard library imports
import json
import os
import uuid
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports
import aiohttp
from dotenv import load_dotenv
from fastapi import WebSocket
import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel

# Local application imports
from utils.stream_response_format import StreamResponse
from utils.ant_client import get_client
from utils.openai_client import get_client as get_openai_client
from utils.research_tools import google_search, extract_content_from_url, batch_extract_content
from utils.prompts import (
    DEEP_RESEARCH_SYSTEM_PROMPT,
    DEEP_RESEARCH_PLAN_PROMPT,
    DEEP_RESEARCH_QUERY_GEN_PROMPT,
    DEEP_RESEARCH_ANALYSIS_PROMPT,
    DEEP_RESEARCH_REPORT_PROMPT
)

load_dotenv()

@dataclass
class deep_research_deps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    agent_responses: Optional[List[StreamResponse]] = None
    # Storage for research results
    storage_path: Optional[str] = None
    # Todo list for tracking research progress
    todo_list_path: Optional[str] = None
    current_todo_item: Optional[str] = None

# Format the system prompt with the current date
formatted_deep_research_system_prompt = DEEP_RESEARCH_SYSTEM_PROMPT.format(
    current_date=datetime.now().strftime('%B %d, %Y')
)

class TodoItem(BaseModel):
    """Model for a research todo item"""
    id: str = Field(description="Unique identifier for the todo item")
    description: str = Field(description="Description of the research task")
    completed: bool = Field(description="Whether the task has been completed", default=False)
    dependencies: List[str] = Field(description="IDs of todo items this item depends on", default_factory=list)
    priority: int = Field(description="Priority of the task (1-5, with 1 being highest)", default=3)
    findings_path: Optional[str] = Field(description="Path to the findings file for this todo item", default=None)
    completion_time: Optional[datetime] = Field(description="When this task was completed", default=None)
    knowledge_gaps: List[str] = Field(description="Knowledge gaps identified during this task", default_factory=list)
    
class ResearchTodo(BaseModel):
    """Model for the research todo list"""
    title: str = Field(description="Title of the research project")
    description: str = Field(description="Description of the research project")
    todo_items: List[TodoItem] = Field(description="List of todo items")
    current_item_id: Optional[str] = Field(description="ID of the currently active todo item", default=None)
    completed_items: List[str] = Field(description="IDs of completed todo items", default_factory=list)
    last_completed_item_id: Optional[str] = Field(description="ID of the most recently completed todo item", default=None)
    knowledge_gaps: List[str] = Field(description="Running list of knowledge gaps across all tasks", default_factory=list)
    report_sections: Dict[str, str] = Field(description="Incremental report sections built after tasks", default_factory=dict)

class SearchQuery(BaseModel):
    """Model for search query generation"""
    query: str = Field(description="The search query string")
    num_results: int = Field(description="Number of results to retrieve (max 10)")

class ResearchGoal(BaseModel):
    """Model for research goals"""
    description: str = Field(description="Description of the research goal")
    completed: bool = Field(description="Whether the goal has been completed", default=False)
    findings: List[str] = Field(description="Key findings related to this goal", default_factory=list)

class ResearchPlan(BaseModel):
    """Model for the overall research plan"""
    goals: List[ResearchGoal] = Field(description="List of research goals")

class ResearchResult(BaseModel):
    """Model for the research result"""
    report: str = Field(description="The comprehensive research report")

# Initialize the Anthropic model
model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    anthropic_client=get_client()
)

# Initialize the Deep Research Agent
deep_research_agent = Agent(
    model=model,
    name="Deep Research Agent",
    system_prompt=formatted_deep_research_system_prompt,
    deps_type=deep_research_deps,
    # result_type=ResearchResult,
    retries=3
)

@deep_research_agent.tool
async def create_research_plan(
    ctx: RunContext[deep_research_deps],
    research_topic: str,
    research_description: str
) -> str:
    """Create a detailed research plan with todo items based on the research topic."""
    try:
        logfire.info(f"Creating research plan for topic: {research_topic}")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Plan: Analyzing topic and creating research plan...")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)

        # Create storage directory if it doesn't exist
        if not ctx.deps.storage_path:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            ctx.deps.storage_path = os.path.join(base_dir, "research_data", f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        os.makedirs(ctx.deps.storage_path, exist_ok=True)
        
        # Set todo list path
        ctx.deps.todo_list_path = os.path.join(ctx.deps.storage_path, "todo.json")
        
        # Use OpenAI gpt-4.1 for planning
        client = get_openai_client()
        
        # Create a prompt for the model to generate a research plan
        plan_prompt = DEEP_RESEARCH_PLAN_PROMPT.format(
            research_topic=research_topic,
            research_description=research_description
        )
        
        # Generate the plan using OpenAI
        response = await client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL_NAME"),
            messages=[{"role": "user", "content": plan_prompt}],
            max_completion_tokens=2000,
            # temperature=0.7
        )

        plan_response = response.choices[0].message.content
        logfire.info(f"plan_response: {plan_response}")
        
        # Extract JSON from response
        match = re.search(r'\{\s*"title".*\}', plan_response, re.DOTALL)
        
        if match:
            plan_json = match.group(0)
            plan_data = json.loads(plan_json)
            
            # Create ResearchTodo object
            todo_list = ResearchTodo(
                title=plan_data.get("title", research_topic),
                description=plan_data.get("description", research_description),
                todo_items=[
                    TodoItem(
                        id=item.get("id", f"task{i+1}"),
                        description=item.get("description", ""),
                        priority=item.get("priority", 3),
                        dependencies=item.get("dependencies", []),
                        completed=False
                    )
                    for i, item in enumerate(plan_data.get("todo_items", []))
                ],
                current_item_id=None,
                completed_items=[]
            )
            
            # Save the todo list to a file
            with open(ctx.deps.todo_list_path, "w") as f:
                f.write(todo_list.model_dump_json(indent=2))
                
            # Create a markdown version for better readability
            markdown_todo = f"# Research Plan: {todo_list.title}\n\n"
            markdown_todo += f"## Description\n{todo_list.description}\n\n"
            markdown_todo += "## Todo Items\n\n"
            
            # Sort items by priority and dependencies
            sorted_items = sorted(todo_list.todo_items, key=lambda x: x.priority)
            
            for item in sorted_items:
                deps = f" (Depends on: {', '.join(item.dependencies)})" if item.dependencies else ""
                markdown_todo += f"- [ ] **Task {item.id}** (Priority: {item.priority}){deps}: {item.description}\n"
                
            # Save markdown version
            with open(os.path.join(ctx.deps.storage_path, "todo.md"), "w") as f:
                f.write(markdown_todo)
            
            # Update stream with plan creation completion
            if ctx.deps.stream_output:
                ctx.deps.stream_output.steps.append(f"Research Plan: Created plan with {len(todo_list.todo_items)} research tasks")
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
            # Return the markdown version for display
            return markdown_todo
            
        else:
            error_msg = "Failed to parse generated research plan as JSON"
            logfire.error(error_msg)
            raise ValueError(error_msg)
            
    except Exception as e:
        error_msg = f"Error creating research plan: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Error: Could not create research plan")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Error: {error_msg}"

@deep_research_agent.tool
async def get_current_todo_item(
    ctx: RunContext[deep_research_deps]
) -> str:
    """Retrieve the next todo item to work on based on dependencies and priority."""
    try:
        logfire.info("Getting next todo item to work on")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Progress: Finding next task to work on...")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        # Check if todo list exists
        if not ctx.deps.todo_list_path or not os.path.exists(ctx.deps.todo_list_path):
            return "Error: No research plan exists. Please create one first with create_research_plan."
            
        # Load the todo list
        with open(ctx.deps.todo_list_path, "r") as f:
            todo_data = json.load(f)
            todo_list = ResearchTodo.model_validate(todo_data)
            
        # Find uncompleted items
        uncompleted = [item for item in todo_list.todo_items if not item.completed]
        
        if not uncompleted:
            return "All research tasks have been completed! You can now generate the final report."
            
        # Filter for items whose dependencies are all completed
        completed_ids = set(todo_list.completed_items)
        
        available_items = []
        for item in uncompleted:
            deps_completed = all(dep in completed_ids for dep in item.dependencies)
            if deps_completed:
                available_items.append(item)
                
        if not available_items:
            return "There are uncompleted tasks, but their dependencies haven't been completed yet."
            
        # Sort by priority
        available_items.sort(key=lambda x: x.priority)
        
        # Select the highest priority item
        next_item = available_items[0]
        
        # Update current item in the todo list
        todo_list.current_item_id = next_item.id
        
        # Save updated todo list
        with open(ctx.deps.todo_list_path, "w") as f:
            f.write(todo_list.model_dump_json(indent=2))
            
        # Update the current item in the context
        ctx.deps.current_todo_item = next_item.id
        
        # Get context from previous completed task if available
        previous_context = ""
        if todo_list.last_completed_item_id:
            previous_item = None
            for item in todo_list.todo_items:
                if item.id == todo_list.last_completed_item_id:
                    previous_item = item
                    break
                    
            if previous_item and previous_item.findings_path and os.path.exists(previous_item.findings_path):
                try:
                    with open(previous_item.findings_path, "r") as f:
                        finding_content = f.read()
                        previous_context = f"\n\n## Previous Findings (from {previous_item.id}: {previous_item.description})\n\n{finding_content}\n\n"
                except Exception as e:
                    logfire.error(f"Error reading previous findings: {str(e)}")
                    previous_context = f"\n\nNote: Could not retrieve previous findings due to an error: {str(e)}\n\n"
                    
        # For tasks with specific dependencies, also include direct dependency context
        dependency_context = ""
        if next_item.dependencies:
            # Get the most recently completed dependency
            dependency_items = []
            for dep_id in next_item.dependencies:
                for item in todo_list.todo_items:
                    if item.id == dep_id and item.completed:
                        dependency_items.append(item)
                        
            if dependency_items:
                # Sort by completion time if available
                dependency_items.sort(key=lambda x: x.completion_time if x.completion_time else datetime.min, reverse=True)
                dep_item = dependency_items[0]
                
                if dep_item.findings_path and os.path.exists(dep_item.findings_path) and dep_item.id != todo_list.last_completed_item_id:
                    try:
                        with open(dep_item.findings_path, "r") as f:
                            finding_content = f.read()
                            dependency_context = f"\n\n## Dependency Findings (from {dep_item.id}: {dep_item.description})\n\n{finding_content}\n\n"
                    except Exception as e:
                        logfire.error(f"Error reading dependency findings: {str(e)}")
        
        # Create progress information
        total_tasks = len(todo_list.todo_items)
        completed_count = len(todo_list.completed_items)
        progress_percent = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
        
        # Create an ASCII progress map
        progress_map = ""
        sorted_items = sorted(todo_list.todo_items, key=lambda x: (len(x.dependencies), x.priority))
        for item in sorted_items:
            if item.id == next_item.id:
                progress_map += "[CURRENT]→"
            elif item.completed:
                progress_map += "[X]→"
            else:
                progress_map += "[ ]→"
        progress_map = progress_map[:-1]  # Remove last arrow
        
        # Find next anticipated tasks
        next_anticipated = []
        for item in uncompleted:
            if item.id != next_item.id:
                dependencies_minus_current = [dep for dep in item.dependencies if dep != next_item.id]
                if all(dep in completed_ids for dep in dependencies_minus_current):
                    next_anticipated.append(item)
        
        next_anticipated.sort(key=lambda x: x.priority)
        coming_next = ""
        if next_anticipated:
            coming_next = "\n\n## Coming Next\n"
            for i, item in enumerate(next_anticipated[:2]):  # Show at most 2 upcoming tasks
                coming_next += f"{i+1}. Task {item.id} (Priority {item.priority}): {item.description}\n"
        
        # Update stream with selected task
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Progress: Working on task {completed_count+1}/{total_tasks} ({int(progress_percent)}%) - {next_item.description}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        # Return information about the selected task with progress and context
        return f"""
        # Research Dashboard: Task {next_item.id} ({completed_count}/{total_tasks}, {progress_percent:.1f}% complete)
        
        {progress_map}
        
        ## Current Task
        ID: {next_item.id}
        Priority: {next_item.priority}
        Dependencies: {', '.join(next_item.dependencies) if next_item.dependencies else 'None'}
        
        Description: {next_item.description}
        {coming_next}
        {previous_context}
        {dependency_context}
        
        ## Knowledge Gaps Identified So Far
        {chr(10).join(f"- {gap}" for gap in todo_list.knowledge_gaps) if todo_list.knowledge_gaps else "No knowledge gaps identified yet."}
        
        You can retrieve full context from all previous tasks by calling retrieve_context() if needed.
        """
        
    except Exception as e:
        error_msg = f"Error getting next todo item: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Error: Could not determine next task")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Error: {error_msg}"

@deep_research_agent.tool
async def mark_todo_item_complete(
    ctx: RunContext[deep_research_deps],
    item_id: str = '',
    findings: str = '',
    knowledge_gaps: list = None,
    report_section: str = None
) -> str:
    """Mark a todo item as complete and store its findings. All parameters except item_id are optional."""
    # Fallbacks for missing fields
    if knowledge_gaps is None:
        knowledge_gaps = []
    if report_section is None:
        report_section = None
    try:
        logfire.info(f"Marking todo item {item_id} as complete")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Progress: Completing task {item_id}...")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        # Check if todo list exists
        if not ctx.deps.todo_list_path or not os.path.exists(ctx.deps.todo_list_path):
            return "Error: No research plan exists. Please create one first with create_research_plan."
            
        # Load the todo list
        with open(ctx.deps.todo_list_path, "r") as f:
            todo_data = json.load(f)
            todo_list = ResearchTodo.model_validate(todo_data)
            
        # Find the item
        item_to_complete = None
        for item in todo_list.todo_items:
            if item.id == item_id:
                item_to_complete = item
                break
                
        if not item_to_complete:
            return f"Error: Task with ID {item_id} not found in the research plan."
            
        if item_to_complete.completed:
            return f"Task {item_id} is already marked as complete."
            
        # Store findings
        findings_filename = f"findings_{item_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        findings_path = os.path.join(ctx.deps.storage_path, findings_filename)
        
        # Process knowledge gaps if provided
        knowledge_gaps_text = ""
        if knowledge_gaps:
            knowledge_gaps_text = "\n\n## Knowledge Gaps Identified\n\n"
            for gap in knowledge_gaps:
                knowledge_gaps_text += f"- {gap}\n"
                
            # Update the todo item's knowledge gaps
            item_to_complete.knowledge_gaps = knowledge_gaps
            
            # Update the global knowledge gaps list
            for gap in knowledge_gaps:
                if gap not in todo_list.knowledge_gaps:
                    todo_list.knowledge_gaps.append(gap)
                    
        # Save the findings with knowledge gaps
        with open(findings_path, "w") as f:
            f.write(f"# Findings for Task {item_id}: {item_to_complete.description}\n\n")
            f.write(findings or "")
            f.write(knowledge_gaps_text)
            
        # Update the item
        for item in todo_list.todo_items:
            if item.id == item_id:
                item.completed = True
                item.findings_path = findings_path
                item.completion_time = datetime.now()
                break
                
        # Add to completed items
        if item_id not in todo_list.completed_items:
            todo_list.completed_items.append(item_id)
            
        # Update last completed item
        todo_list.last_completed_item_id = item_id
            
        # Reset current item if it's the one being completed
        if todo_list.current_item_id == item_id:
            todo_list.current_item_id = None
            ctx.deps.current_todo_item = None
            
        # Store report section if provided
        if report_section:
            todo_list.report_sections[item_id] = report_section
            
        # Save updated todo list
        with open(ctx.deps.todo_list_path, "w") as f:
            f.write(todo_list.model_dump_json(indent=2))
            
        # Update the markdown version
        markdown_todo = f"# Research Plan: {todo_list.title}\n\n"
        markdown_todo += f"## Description\n{todo_list.description}\n\n"
        markdown_todo += f"## Progress: {len(todo_list.completed_items)}/{len(todo_list.todo_items)} tasks completed\n\n"
        markdown_todo += "## Todo Items\n\n"
        
        # Sort items by priority and dependencies
        sorted_items = sorted(todo_list.todo_items, key=lambda x: x.priority)
        
        for item in sorted_items:
            deps = f" (Depends on: {', '.join(item.dependencies)})" if item.dependencies else ""
            checkbox = "[x]" if item.completed else "[ ]"
            completion_info = f" - Completed: {item.completion_time.strftime('%Y-%m-%d %H:%M')}" if item.completed and item.completion_time else ""
            markdown_todo += f"- {checkbox} **Task {item.id}** (Priority: {item.priority}){deps}: {item.description}{completion_info}\n"
            
        # Add knowledge gaps section
        if todo_list.knowledge_gaps:
            markdown_todo += "\n## Knowledge Gaps Identified\n\n"
            for gap in todo_list.knowledge_gaps:
                markdown_todo += f"- {gap}\n"
                
        # Save markdown version
        with open(os.path.join(ctx.deps.storage_path, "todo.md"), "w") as f:
            f.write(markdown_todo)
            
        # Update stream with completion
        if ctx.deps.stream_output:
            completed_count = len(todo_list.completed_items)
            total_tasks = len(todo_list.todo_items)
            progress_percent = round((completed_count / total_tasks) * 100) if total_tasks > 0 else 0
            ctx.deps.stream_output.steps.append(f"Research Progress: Task {item_id} completed ({completed_count}/{total_tasks} tasks, {progress_percent}%)")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        # Calculate progress
        total_items = len(todo_list.todo_items)
        completed_items = len(todo_list.completed_items)
        progress_percent = (completed_items / total_items) * 100 if total_items > 0 else 0
            
        # Find next available tasks
        available_next = []
        completed_ids = set(todo_list.completed_items)
        
        for item in todo_list.todo_items:
            if not item.completed and all(dep in completed_ids for dep in item.dependencies):
                available_next.append(item)
                
        available_next.sort(key=lambda x: x.priority)
        next_tasks_text = ""
        
        if available_next:
            next_tasks_text = "\n\n## Available Next Tasks\n"
            for i, item in enumerate(available_next[:3]):  # Show up to 3 available tasks
                next_tasks_text += f"{i+1}. Task {item.id} (Priority {item.priority}): {item.description}\n"
        else:
            next_tasks_text = "\n\nNo tasks are currently available to work on."
            
        return f"""
        # Task {item_id} Completed Successfully!
        
        Findings have been saved to: {findings_filename}
        Research progress: {completed_items}/{total_items} tasks completed ({progress_percent:.1f}%)
        
        {next_tasks_text}
        
        You can get the next task using get_current_todo_item.
        """
        
    except Exception as e:
        error_msg = f"Error marking todo item as complete: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Error: Could not complete task {item_id}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Error: {error_msg}"

@deep_research_agent.tool
async def generate_search_queries(
    ctx: RunContext[deep_research_deps],
    research_goals: List[str],
    previous_findings: Optional[str] = None
) -> str:
    """Generate optimized search queries based on research goals"""
    try:
        logfire.info(f"Generating search queries")

        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Generating targeted search queries...")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)

        # Use Claude directly through the client instead of model.generate
        client = get_client()

        # Create a prompt for the model to generate queries
        query_gen_prompt = DEEP_RESEARCH_QUERY_GEN_PROMPT.format(
            research_goals=json.dumps(research_goals, indent=2),
            previous_findings=previous_findings or "No previous findings yet."
        )

        # Use the Anthropic client directly
        response = await client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL_NAME"),
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {"role": "user", "content": query_gen_prompt}
            ]
        )
        query_response = response.content[0].text

        # Extract JSON from response
        import re
        match = re.search(r'\[\s*\{.*\}\s*\]', query_response, re.DOTALL)
        
        if match:
            queries_json = match.group(0)
            queries = json.loads(queries_json)
            
            # Format the queries for logging and display
            formatted_queries = "Generated Search Queries:\n"
            for i, query in enumerate(queries):
                formatted_queries += f"{i+1}. Query: '{query.get('query')}'\n"
                formatted_queries += f"   Results to fetch: {query.get('num_results', 10)}\n"
            
            logfire.info(formatted_queries)
            
            # Update stream with generated queries
            if ctx.deps.stream_output:
                ctx.deps.stream_output.steps.append(f"Research Process: Generated {len(queries)} search queries")
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
            return json.dumps(queries)
        else:
            error_msg = "Failed to parse generated queries as JSON"
            logfire.error(error_msg)
            raise ValueError(error_msg)
            
    except Exception as e:
        error_msg = f"Error generating search queries: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Failed to generate search queries")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return json.dumps([{"query": f"Error: {str(e)}", "num_results": 5}])

@deep_research_agent.tool
async def execute_search(
    ctx: RunContext[deep_research_deps],
    query: str,
    num_results: int = 10
) -> str:
    """Execute a search query using the Google Search API"""
    try:
        logfire.info(f"Executing search query: '{query}'")
        
        # Update stream with status
        if ctx.deps.stream_output:
            # Truncate long queries for display
            display_query = query if len(query) < 60 else query[:57] + "..."
            ctx.deps.stream_output.steps.append(f"Research Process: Searching for '{display_query}'")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Use the utility function from research_tools.py instead of API
        search_results = await google_search(query, num_results)
        
        # Update stream with search completion
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Search completed")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return search_results
    
    except Exception as e:
        error_msg = f"Error executing search: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Search failed")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Error performing search: {error_msg}"

@deep_research_agent.tool
async def extract_web_content(
    ctx: RunContext[deep_research_deps],
    url: str,
    user_query: Optional[str] = None
) -> str:
    """Extract content from a web page URL using crawl4ai"""
    try:
        logfire.info(f"Extracting content from URL: '{url}'")
        
        # Update stream with status
        if ctx.deps.stream_output:
            # Extract and display domain instead of full URL
            domain = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
            ctx.deps.stream_output.steps.append(f"Research Process: Extracting content from {domain}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Use the utility function from research_tools.py
        content = await extract_content_from_url(url, user_query)
        
        # Update stream with extraction completion
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Content extracted successfully")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return content
    
    except Exception as e:
        error_msg = f"Error extracting content: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not extract content")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Error extracting content: {error_msg}"

@deep_research_agent.tool
async def batch_extract_web_content(
    ctx: RunContext[deep_research_deps],
    urls: List[str],
    user_query: Optional[str] = None
) -> str:
    """Extract content from multiple web page URLs in parallel"""
    try:
        logfire.info(f"Batch extracting content from {len(urls)} URLs")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Process: Extracting content from {len(urls)} sources")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Use the utility function from research_tools.py
        content_map = await batch_extract_content(urls, user_query)
        
        # Format the results for easier reading
        formatted_results = "### Extracted Content Summary\n\n"
        for url, content in content_map.items():
            # Add a header for each URL
            formatted_results += f"## Content from {url}\n\n"
            
            # Add a preview of the content (first 500 chars)
            preview = content[:500] + "..." if len(content) > 500 else content
            formatted_results += f"{preview}\n\n"
            
            # Add a separator
            formatted_results += "---\n\n"
        
        # Store full content to files for later retrieval
        if ctx.deps.storage_path:
            # Create a subdirectory for batch extraction
            batch_dir = os.path.join(ctx.deps.storage_path, f"batch_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(batch_dir, exist_ok=True)
            
            # Save each content to a separate file
            for i, (url, content) in enumerate(content_map.items()):
                # Create a valid filename from the URL
                filename = re.sub(r'[^\w\-_]', '_', url)[:100]  # Truncate to reasonable length
                filepath = os.path.join(batch_dir, f"{i+1}_{filename}.md")
                
                with open(filepath, "w") as f:
                    f.write(f"# Content from {url}\n\n{content}")
                
            formatted_results += f"\nFull content saved to {batch_dir}\n"
        
        # Update stream with extraction completion
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Process: Successfully extracted content from {len(urls)} sources")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return formatted_results
    
    except Exception as e:
        error_msg = f"Error in batch content extraction: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Batch content extraction failed")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Error extracting content: {error_msg}"

@deep_research_agent.tool
async def analyze_search_results(
    ctx: RunContext[deep_research_deps],
    search_results: str,
    research_goals: List[str]
) -> str:
    """Analyze search results to extract relevant information"""
    try:
        logfire.info("Analyzing search results")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Analyzing search results")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Extract URLs from the search results for potential content extraction
        urls = []
        for line in search_results.split('\n'):
            if line.startswith("URL: "):
                url = line[5:].strip()
                if url and url.startswith(('http://', 'https://')):
                    urls.append(url)
        
        # Create a prompt for the model to analyze results
        analysis_prompt = DEEP_RESEARCH_ANALYSIS_PROMPT.format(
            research_goals=json.dumps(research_goals, indent=2),
            search_results=search_results,
            urls=json.dumps(urls, indent=2)
        )
        
        # Use the model to analyze search results
        client = get_client()
        response = await client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL_NAME"),
            max_tokens=2000,
            temperature=0.3,
            messages=[
                {"role": "user", "content": analysis_prompt}
            ]
        )
        analysis_response = response.content[0].text
        
        # Extract JSON from response
        import re
        match = re.search(r'\{\s*"relevant_findings".*\}', analysis_response, re.DOTALL)
        
        if match:
            analysis_json = match.group(0)
            analysis = json.loads(analysis_json)
            
            # Update stream with analysis completion
            if ctx.deps.stream_output:
                ctx.deps.stream_output.steps.append("Research Process: Search results analyzed")
                
                # Add additional information about URLs to explore
                urls_to_explore = analysis.get("urls_to_explore", [])
                if urls_to_explore and len(urls_to_explore) > 0:
                    ctx.deps.stream_output.steps.append(f"Research Process: Identified {len(urls_to_explore)} promising sources")
                
                await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
            return json.dumps(analysis)
        else:
            error_msg = "Failed to parse analysis results as JSON"
            logfire.error(error_msg)
            
            # Try to return whatever we got as a fallback
            return json.dumps({
                "relevant_findings": "Analysis could not be properly formatted. Raw output: " + analysis_response[:500],
                "knowledge_gaps": [],
                "urls_to_explore": [],
                "follow_up_queries": []
            })
            
    except Exception as e:
        error_msg = f"Error analyzing search results: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not analyze search results")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return json.dumps({
            "relevant_findings": f"Error during analysis: {str(e)}",
            "knowledge_gaps": [],
            "urls_to_explore": [],
            "follow_up_queries": []
        })

@deep_research_agent.tool
async def store_research_findings(
    ctx: RunContext[deep_research_deps],
    findings: str
) -> str:
    """Store research findings for later synthesis"""
    try:
        logfire.info(f"Storing research findings")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Storing research findings")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Ensure storage path exists
        if not ctx.deps.storage_path:
            # Create a default storage path
            base_dir = os.path.abspath(os.path.dirname(__file__))
            ctx.deps.storage_path = os.path.join(base_dir, "research_data", f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        os.makedirs(ctx.deps.storage_path, exist_ok=True)
        
        # Parse the findings if it's JSON
        try:
            findings_dict = json.loads(findings)
            
            # Convert to markdown format
            markdown_content = f"# Research Findings\n\n"
            
            # Add relevant findings
            markdown_content += "## Relevant Findings\n\n"
            if "relevant_findings" in findings_dict:
                markdown_content += findings_dict["relevant_findings"] + "\n\n"
            
            # Add knowledge gaps
            markdown_content += "## Knowledge Gaps\n\n"
            if "knowledge_gaps" in findings_dict:
                if isinstance(findings_dict["knowledge_gaps"], list):
                    for gap in findings_dict["knowledge_gaps"]:
                        markdown_content += f"- {gap}\n"
                else:
                    markdown_content += findings_dict["knowledge_gaps"] + "\n"
            markdown_content += "\n"
            
            # Add URLs to explore
            markdown_content += "## URLs to Explore\n\n"
            if "urls_to_explore" in findings_dict and isinstance(findings_dict["urls_to_explore"], list):
                for url in findings_dict["urls_to_explore"]:
                    markdown_content += f"- {url}\n"
            markdown_content += "\n"
            
            # Add follow-up queries
            markdown_content += "## Follow-up Queries\n\n"
            if "follow_up_queries" in findings_dict and isinstance(findings_dict["follow_up_queries"], list):
                for query in findings_dict["follow_up_queries"]:
                    markdown_content += f"- {query}\n"
            
            # Write findings to a markdown file
            findings_file = os.path.join(ctx.deps.storage_path, f"findings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(findings_file, "w") as f:
                f.write(markdown_content)
        except json.JSONDecodeError:
            # If it's not valid JSON, just write the raw content to a file
            findings_file = os.path.join(ctx.deps.storage_path, f"findings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(findings_file, "w") as f:
                f.write(f"# Research Findings\n\n{findings}")
        
        # Update stream with storage completion
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Findings stored")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Research findings stored at {findings_file}"
    
    except Exception as e:
        error_msg = f"Error storing research findings: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not store findings")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Failed to store research findings: {error_msg}"

@deep_research_agent.tool
async def retrieve_context(
    ctx: RunContext[deep_research_deps],
    max_tokens: int = 8000
) -> str:
    """Retrieve context from previously completed todo items."""
    try:
        logfire.info("Retrieving research context from completed todo items")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Process: Retrieving context from previous research")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Check if todo list exists
        if not ctx.deps.todo_list_path or not os.path.exists(ctx.deps.todo_list_path):
            return "No research plan exists. Please create one first with create_research_plan."
            
        # Load the todo list
        with open(ctx.deps.todo_list_path, "r") as f:
            todo_data = json.load(f)
            todo_list = ResearchTodo.model_validate(todo_data)
            
        # Get all completed todo items
        completed_items = [item for item in todo_list.todo_items if item.completed]
        
        if not completed_items:
            return "No completed research tasks found yet."
            
        # Get findings from completed items
        all_findings = []
        
        for item in completed_items:
            if item.findings_path and os.path.exists(item.findings_path):
                try:
                    with open(item.findings_path, "r") as f:
                        finding_content = f.read()
                        all_findings.append(f"## Findings from Task {item.id}: {item.description}\n\n{finding_content}\n\n")
                except Exception as e:
                    logfire.error(f"Error reading findings for task {item.id}: {str(e)}")
                    all_findings.append(f"## Task {item.id}: {item.description}\n\nError reading findings: {str(e)}\n\n")
        
        # Combine findings
        combined_findings = "\n".join(all_findings)
        
        # Simple token estimation (rough approximation)
        tokens_per_char = 0.25  # Rough estimate
        estimated_tokens = len(combined_findings) * tokens_per_char
        
        # Truncate if too long (simple approach - in practice, would use a better tokenizer)
        if estimated_tokens > max_tokens:
            truncation_factor = max_tokens / estimated_tokens
            truncation_length = int(len(combined_findings) * truncation_factor)
            combined_findings = combined_findings[:truncation_length] + "\n...[additional context truncated]..."
        
        # Update stream
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Process: Retrieved context from {len(completed_items)} completed tasks")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return combined_findings
    
    except Exception as e:
        error_msg = f"Error retrieving research context: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not retrieve context")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        return f"Failed to retrieve research context: {error_msg}"

@deep_research_agent.tool
async def get_specific_task_context(
    ctx: RunContext[deep_research_deps],
    task_id: str
) -> str:
    """Retrieve context from a specific completed todo item."""
    try:
        logfire.info(f"Retrieving context from specific task: {task_id}")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Process: Retrieving context from task {task_id}...")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        # Check if todo list exists
        if not ctx.deps.todo_list_path or not os.path.exists(ctx.deps.todo_list_path):
            return "No research plan exists. Please create one first with create_research_plan."
            
        # Load the todo list
        with open(ctx.deps.todo_list_path, "r") as f:
            todo_data = json.load(f)
            todo_list = ResearchTodo.model_validate(todo_data)
            
        # Find the specific task
        task_item = None
        for item in todo_list.todo_items:
            if item.id == task_id:
                task_item = item
                break
                
        if not task_item:
            return f"Error: Task with ID {task_id} not found in the research plan."
            
        if not task_item.completed:
            return f"Error: Task {task_id} has not been completed yet, so no findings are available."
            
        if not task_item.findings_path or not os.path.exists(task_item.findings_path):
            return f"Error: No findings file exists for task {task_id}."
            
        # Get findings from the task
        with open(task_item.findings_path, "r") as f:
            finding_content = f.read()
            
        # Get the task's direct dependencies for context
        dependency_contexts = []
        for dep_id in task_item.dependencies:
            dep_item = None
            for item in todo_list.todo_items:
                if item.id == dep_id and item.completed:
                    dep_item = item
                    break
                    
            if dep_item and dep_item.findings_path and os.path.exists(dep_item.findings_path):
                try:
                    with open(dep_item.findings_path, "r") as f:
                        dep_content = f.read()
                        dependency_contexts.append(f"## Context from Dependency {dep_id}: {dep_item.description}\n\n{dep_content}\n\n")
                except Exception as e:
                    logfire.error(f"Error reading dependency findings: {str(e)}")
                    
        # Combine the contexts
        combined_context = f"# Findings from Task {task_id}: {task_item.description}\n\n{finding_content}\n\n"
        
        if dependency_contexts:
            combined_context += "# Related Dependency Contexts\n\n"
            combined_context += "\n".join(dependency_contexts)
            
        # Update stream
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append(f"Research Process: Retrieved context from task {task_id}")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return combined_context
            
    except Exception as e:
        error_msg = f"Error retrieving task context: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not retrieve context")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
            
        return f"Failed to retrieve task context: {error_msg}"

@deep_research_agent.tool
async def generate_research_report(
    ctx: RunContext[deep_research_deps]
) -> str:
    """Generate a comprehensive research report from all completed todo items."""
    try:
        logfire.info("Generating comprehensive research report")
        
        # Update stream with status
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Final Step: Generating comprehensive research report")
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Check if todo list exists
        if not ctx.deps.todo_list_path or not os.path.exists(ctx.deps.todo_list_path):
            return "Error: No research plan exists. Please create one first with create_research_plan."
            
        # Load the todo list
        with open(ctx.deps.todo_list_path, "r") as f:
            todo_data = json.load(f)
            todo_list = ResearchTodo.model_validate(todo_data)
        
        # Check if all tasks are completed
        uncompleted = [item for item in todo_list.todo_items if not item.completed]
        if uncompleted:
            return f"Cannot generate final report yet. There are still {len(uncompleted)} uncompleted tasks."
        
        # Gather all findings from completed tasks
        all_findings = []
        
        # Sort todo items in a logical order (by priority and dependencies)
        sorted_items = sorted(todo_list.todo_items, key=lambda x: (x.priority, len(x.dependencies)))
        
        for item in sorted_items:
            if item.findings_path and os.path.exists(item.findings_path):
                try:
                    with open(item.findings_path, "r") as f:
                        finding_content = f.read()
                        all_findings.append(f"## Findings from Task {item.id}: {item.description}\n\n{finding_content}\n\n")
                except Exception as e:
                    logfire.error(f"Error reading findings for task {item.id}: {str(e)}")
                    all_findings.append(f"## Task {item.id}: {item.description}\n\nError reading findings: {str(e)}\n\n")
        
        # Combine all findings
        combined_findings = "\n".join(all_findings)
        
        # Check if we have incremental report sections
        has_report_sections = len(todo_list.report_sections) > 0
        report_sections_text = ""
        
        if has_report_sections:
            # Build an ordered list of sections based on task completion order
            section_items = []
            for task_id in todo_list.completed_items:
                if task_id in todo_list.report_sections:
                    task_item = None
                    for item in todo_list.todo_items:
                        if item.id == task_id:
                            task_item = item
                            break
                    
                    if task_item:
                        section_items.append((task_item, todo_list.report_sections[task_id]))
            
            # Sort by completion time if available
            section_items.sort(key=lambda x: x[0].completion_time if x[0].completion_time else datetime.min)
            
            # Build the sections text
            report_sections_text = "\n\n## Incremental Report Sections\n\n"
            for item, section in section_items:
                report_sections_text += f"### Section from Task {item.id}: {item.description}\n\n{section}\n\n"
        
        # Update report prompt to use DEEP_RESEARCH_REPORT_PROMPT
        report_sections_text = report_sections_text if has_report_sections else ''
        report_sections_instruction = 'Use the research findings to enhance and expand upon the report sections provided.' if has_report_sections else ''
        
        # Use OpenAI gpt-4.1 for report generation
        client = get_openai_client()
        report_prompt = DEEP_RESEARCH_REPORT_PROMPT.format(
            research_title=todo_list.title,
            research_description=todo_list.description,
            report_sections_text=report_sections_text if has_report_sections else '',
            report_sections_instruction=report_sections_instruction,
            combined_findings=combined_findings,
            knowledge_gaps=json.dumps(todo_list.knowledge_gaps)
        )
        response = await client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL_NAME"),
            messages=[{"role": "user", "content": report_prompt}],
            max_completion_tokens=15000,
            # temperature=0.3
        )
        report = response.choices[0].message.content
        
        # Save the report
        if ctx.deps.storage_path:
            report_file = os.path.join(ctx.deps.storage_path, "final_report.md")
            with open(report_file, "w") as f:
                f.write(f"# {todo_list.title}: Research Report\n\n")
                f.write(report)
            logfire.info(f"Report saved to {report_file}")
        
        # Update stream with completion
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Research Complete: Final report generated successfully")
            ctx.deps.stream_output.output = report
            ctx.deps.stream_output.status_code = 200
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Return a string (not a dict) for compatibility when result_type is not set
        return f"# {todo_list.title}: Research Report\n\n{report}"
    
    except Exception as e:
        error_msg = f"Error generating research report: {str(e)}"
        logfire.error(error_msg, exc_info=True)
        
        # Update stream with error
        if ctx.deps.stream_output:
            ctx.deps.stream_output.steps.append("Error: Could not generate research report")
            ctx.deps.stream_output.status_code = 500
            await _safe_websocket_send(ctx.deps.websocket, ctx.deps.stream_output)
        
        # Return a string error for compatibility
        return f"Failed to generate research report: {error_msg}"

# Helper function for sending WebSocket messages
async def _safe_websocket_send(websocket: Optional[WebSocket], message: Any) -> bool:
    """Safely send message through websocket with error handling"""
    try:
        if websocket and hasattr(websocket, 'client_state') and websocket.client_state.CONNECTED:
            await websocket.send_text(json.dumps(asdict(message)))
            return True
        return False
    except Exception as e:
        logfire.error(f"WebSocket send failed: {str(e)}")
        return False 