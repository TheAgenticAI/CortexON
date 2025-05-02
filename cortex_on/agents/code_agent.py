# Standard library imports
import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

# Third-party imports
from dotenv import load_dotenv
import logfire
from fastapi import WebSocket
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

# Local application imports
from utils.ant_client import get_client
from utils.stream_response_format import StreamResponse
from utils.code_formatter import format_execution_result
from utils.docker_executor import run_code

load_dotenv()


@dataclass
class CoderAgentDeps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    session_id: Optional[str] = None  # Add session_id for persistent Docker environment

# Language-specific file extensions
LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "java": ".java",
    "cpp": ".cpp",
    "javascript": ".js",
    "typescript": ".ts",
    "ruby": ".rb",
    "go": ".go",
    "rust": ".rs",
    "php": ".php"
}
class CoderResult(BaseModel):
    dependencies: List = Field(
        description="All the packages name that has to be installed before the code execution"
    )
    content: str = Field(description="Response content in the form of code")
    code_description: str = Field(description="Description of the code")

coder_system_message = """You are a helpful AI assistant with advanced coding capabilities. Solve tasks using your coding and language skills.

<critical>
    - You have access to a secure Docker-based code execution system that runs your code in isolated containers.
    - Each programming language has its own dedicated persistent container.
    - All code executes in a secure, isolated environment with limited resources.
    - Never use interactive input functions like 'input()' in Python or 'read' in Bash.
    - All code must be non-interactive and should execute completely without user interaction.
    - Use command line arguments, environment variables, or file I/O instead of interactive input.
</critical>

You have access to the following tools for code execution and file management:

1. execute_code(language: str, code: str) - Execute code directly in the appropriate language container
   - The code is saved to a file named program.<ext> and executed
   - Supported languages: python, java, cpp, javascript, typescript, ruby, go, rust, php
   - Resources: 0.5 CPU core, 512MB RAM, 30 second timeout

2. create_file(filename: str, content: str, language: str = None) - Create a new file in the container
   - Filename should include appropriate extension (e.g., 'utils.py', 'data.json')
   - Language is optional and will be detected from the file extension

3. read_file(filename: str) - Read the content of an existing file in the container
   - Returns the content of the specified file

4. list_files() - List all files currently in the container
   - Shows what files you've created and can access

5. execute_file(filename: str, language: str = None) - Execute a specific file in the container
   - Use this to run files you've previously created
   - Language is optional and will be detected from the file extension

Each language container persists during your session, so you can:
- Create multiple files that work together
- Build more complex applications with separate modules
- Execute different files as needed
- Modify files based on execution results

Follow this workflow for efficient coding:
1. Break down complex problems into manageable components
2. Create separate files for different modules when appropriate
3. Execute code to test and verify your implementation
4. Organize your code according to best practices for the language

Supported programming languages:

1. Python (.py) - Python 3.11 with numpy, pandas, matplotlib
2. Java (.java) - OpenJDK 17
3. C++ (.cpp) - GCC 11
4. JavaScript (.js) - Node.js 18 with axios
5. TypeScript (.ts) - Node.js 18 with typescript
6. Ruby (.rb) - Ruby 3.2
7. Go (.go) - Go 1.20
8. Rust (.rs) - Rust 1.70
9. PHP (.php) - PHP 8.2

Code guidelines:
- Provide clean, well-structured code that follows language conventions
- Include appropriate error handling
- Use clear naming conventions and add comments for complex logic
- Structure multi-file projects appropriately based on language best practices
- For languages that require the filenames same as the class names, make sure to create the files with the same name as the class name.

Example multi-file workflow:
1. Create a main file with core functionality
2. Create utility files for helper functions
3. Import/include utilities in the main file
4. Execute the main file to run the complete application

Output explanation guidelines:
- After code execution, structure your explanation according to the CoderResult format
- For each code solution, explain:
  1. Dependencies: List all packages that must be installed before executing the code
  2. Content: The actual code across all files you created
  3. Code description: A clear explanation of how the code works, its approach, and file relationships

Example structure:
Dependencies:
- numpy
- pandas

Content:
[The complete code solution, with file relationships explained]

Code Description:
This solution implements [approach] to solve [problem] using [N] files:
- main.py: Handles the core functionality, including [key components]
- utils.py: Contains helper functions for [specific tasks]
The implementation handles [edge cases] by [specific technique].
"""

async def send_stream_update(ctx: RunContext[CoderAgentDeps], message: str) -> None:
    """Helper function to send websocket updates if available"""
    if ctx.deps.websocket and ctx.deps.stream_output:
        ctx.deps.stream_output.steps.append(message)
        await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
        stream_output_json = json.dumps(asdict(ctx.deps.stream_output))
        logfire.debug("WebSocket message sent: {stream_output_json}", stream_output_json=stream_output_json)

# Initialize the model
provider = AnthropicProvider(api_key=os.environ.get("ANTHROPIC_API_KEY")) 

model = AnthropicModel(
    model_name=os.environ.get("ANTHROPIC_MODEL_NAME"),
    provider = provider
)

# Initialize the agent
coder_agent = Agent(
    model=model,
    name="Coder Agent",
    result_type=CoderResult,
    deps_type=CoderAgentDeps,
    system_prompt=coder_system_message
)

@coder_agent.tool
async def execute_code(ctx: RunContext[CoderAgentDeps], language: str, code: str) -> str:
    """
    Executes code in a secure Docker container with resource limits and isolation.
    This tool handles various programming languages with appropriate execution environments.
    
    Args:
        language: The programming language of the code (python, java, cpp)
        code: The source code to execute
        
    Returns:
        The execution results, including stdout, stderr, and status
    """
    try:
        # Normalize language name
        language = language.lower().strip()
        
        # Map language aliases to standard names
        language_mapping = {
            "python3": "python",
            "py": "python",
            "c++": "cpp",
            "node": "javascript",
            "nodejs": "javascript",
            "js": "javascript",
            "rb": "ruby",
            "golang": "go",
            "rust": "rust",
            "php": "php",
            "ts": "typescript",
        }
        
        normalized_language = language_mapping.get(language, language)
        
        # Check if the language is supported
        if normalized_language not in ["python", "java", "cpp", "javascript", "ruby", "go", "rust", "php", "typescript"]:
            error_msg = f"Unsupported language: {normalized_language}."
            await send_stream_update(ctx, error_msg)
            return error_msg
        
        # Send operation description message
        await send_stream_update(ctx, f"Executing {normalized_language} code in secure container")
        
        logfire.info(f"Executing {normalized_language} code in Docker container")
        
        # Store the source code in the StreamResponse
        if ctx.deps.stream_output:
            ctx.deps.stream_output.source_code = code
            ctx.deps.stream_output.metadata = {"language": normalized_language}
        
        # Run the code in a Docker container - we don't need session_id anymore with the new language-based approach
        result = await run_code(normalized_language, code)
        
        # If there was an error with the Docker execution itself
        if "error" in result:
            error_message = result["error"]
            await send_stream_update(ctx, f"Code execution failed: {error_message}")
            logfire.error(f"Code execution failed: {error_message}")
            
            # Create a manually crafted formatted output with error
            formatted_output = f"```{normalized_language}\n{code}\n```\n\n"
            formatted_output += f"## Errors\n\n```\n{error_message}\n```\n\n"
            formatted_output += "## Status\n\n**❌ Execution failed**"
            
            # Update the StreamResponse with both code and formatted error
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = formatted_output
                ctx.deps.stream_output.status_code = 500
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return f"Error: {error_message}"
        
        # Ensure stdout and stderr are strings
        if "stdout" not in result or result["stdout"] is None:
            result["stdout"] = ""
        if "stderr" not in result or result["stderr"] is None:
            result["stderr"] = ""
            
        # Format the execution results for console output
        output = f"Execution results:\n\n"
        
        # Add stdout if available
        if result.get("stdout"):
            output += f"--- Output ---\n{result['stdout']}\n\n"
        else:
            output += "--- No Output ---\n\n"
        
        # Add stderr if there were errors
        if result.get("stderr"):
            output += f"--- Errors ---\n{result['stderr']}\n\n"
        
        # Add execution status
        if result.get("success", False):
            await send_stream_update(ctx, f"{normalized_language.capitalize()} code executed successfully")
            output += "Status: Success\n"
        else:
            await send_stream_update(ctx, f"{normalized_language.capitalize()} code execution failed")
            output += f"Status: Failed (Exit code: {result.get('exit_code', 'unknown')})\n"
        
        # Create a manually crafted formatted output for UI display
        formatted_output = ""
        
        # Always add code section first with proper language syntax highlighting
        formatted_output += f"## Code\n\n```{normalized_language}\n{code}\n```\n\n"
        
        # Add execution results section
        formatted_output += "## Output\n\n"
        if result.get("stdout"):
            formatted_output += f"```\n{result['stdout']}\n```\n\n"
        else:
            formatted_output += "*No output captured*\n\n"
        
        # Add errors section if needed
        if result.get("stderr"):
            formatted_output += f"## Errors\n\n```\n{result['stderr']}\n```\n\n"
        
        # Add status section
        if result.get("success", False):
            formatted_output += "## Status\n\n**✅ Execution completed successfully**"
        else:
            exit_code = result.get("exit_code", "unknown")
            formatted_output += f"## Status\n\n**❌ Execution failed** (Exit code: {exit_code})"
        
        # Update the StreamResponse with both code and results
        if ctx.deps.websocket and ctx.deps.stream_output:
            ctx.deps.stream_output.output = formatted_output
            ctx.deps.stream_output.status_code = 200 if result.get("success", False) else 500
            ctx.deps.stream_output.metadata = {
                "language": normalized_language,
                "success": result.get("success", False),
                "exit_code": result.get("exit_code", "unknown")
            }
            await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
        
        logfire.info(f"Code execution completed with status: {result.get('success', False)}")
        return output
        
    except Exception as e:
        error_msg = f"Error during code execution: {str(e)}"
        await send_stream_update(ctx, "Code execution failed")
        logfire.error(error_msg, exc_info=True)
        
        # Create a manually crafted formatted output with error
        formatted_error = f"```{language}\n{code}\n```\n\n"
        formatted_error += f"## Errors\n\n```\n{error_msg}\n```\n\n"
        formatted_error += "## Status\n\n**❌ Execution failed**"
        
        # Update the StreamResponse with both code and formatted error
        if ctx.deps.websocket and ctx.deps.stream_output:
            ctx.deps.stream_output.output = formatted_error
            ctx.deps.stream_output.status_code = 500
            await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
        
        return error_msg

@coder_agent.tool
async def create_file(ctx: RunContext[CoderAgentDeps], filename: str, content: str, language: str = None) -> str:
    """
    Creates a file in the persistent Docker environment.
    
    Args:
        filename: Name of the file to create
        content: Content to write to the file
        language: Optional programming language for syntax highlighting
        
    Returns:
        Result of the file creation operation
    """
    try:
        # Detect language from filename extension if not provided
        if not language and "." in filename:
            ext = os.path.splitext(filename)[1].lower()
            language_map = {v: k for k, v in LANGUAGE_EXTENSIONS.items()}
            language = language_map.get(ext, None)
        
        # Send operation description message
        await send_stream_update(ctx, f"Creating file: {filename}")
        
        logfire.info(f"Creating file {filename} in Docker environment")
        
        # Get Docker environment
        from utils.docker_executor import get_environment
        env = get_environment(language or "python")
        
        # Connect to Docker environment
        connect_result = await env.connect()
        if not connect_result.get("success", False):
            error_message = connect_result.get("error", "Unable to connect to Docker environment")
            await send_stream_update(ctx, f"Failed to connect to environment: {error_message}")
            return f"Error: {error_message}"
        
        # Write file to Docker environment
        result = await env.write_file(filename, content)
        
        if result.get("success", False):
            message = f"File {filename} created successfully"
            await send_stream_update(ctx, message)
            
            # Format output for frontend display
            formatted_output = f"## File Creation\n\n**{filename}** has been created successfully.\n\n"
            if language:
                formatted_output += f"```{language}\n{content}\n```"
            else:
                formatted_output += f"```\n{content}\n```"
            
            # Update StreamResponse with formatted result
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = formatted_output
                ctx.deps.stream_output.status_code = 200
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return message
        else:
            error_message = result.get("error", "Unknown error")
            await send_stream_update(ctx, f"Failed to create file: {error_message}")
            
            # Update StreamResponse with error
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = f"## Error\n\nFailed to create file {filename}: {error_message}"
                ctx.deps.stream_output.status_code = 500
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return f"Error: {error_message}"
            
    except Exception as e:
        error_msg = f"Error creating file {filename}: {str(e)}"
        await send_stream_update(ctx, f"File creation failed: {str(e)}")
        logfire.error(error_msg, exc_info=True)
        return error_msg

@coder_agent.tool
async def read_file(ctx: RunContext[CoderAgentDeps], filename: str) -> str:
    """
    Reads a file from the persistent Docker environment.
    
    Args:
        filename: Name of the file to read
        
    Returns:
        Content of the file or error message
    """
    try:
        # Detect language from filename extension for environment selection
        language = "python"  # Default
        if "." in filename:
            ext = os.path.splitext(filename)[1].lower()
            language_map = {v: k for k, v in LANGUAGE_EXTENSIONS.items()}
            detected_lang = language_map.get(ext, None)
            if detected_lang:
                language = detected_lang
        
        # Send operation description message
        await send_stream_update(ctx, f"Reading file: {filename}")
        
        logfire.info(f"Reading file {filename} from Docker environment")
        
        # Get Docker environment
        from utils.docker_executor import get_environment
        env = get_environment(language)
        
        # Connect to Docker environment
        connect_result = await env.connect()
        if not connect_result.get("success", False):
            error_message = connect_result.get("error", "Unable to connect to Docker environment")
            await send_stream_update(ctx, f"Failed to connect to environment: {error_message}")
            return f"Error: {error_message}"
        
        # Read file from Docker environment
        result = await env.read_file(filename)
        
        if result.get("success", False):
            content = result.get("content", "")
            await send_stream_update(ctx, f"File {filename} read successfully")
            
            # Format output for frontend display
            formatted_output = f"## File: {filename}\n\n"
            if language:
                formatted_output += f"```{language}\n{content}\n```"
            else:
                formatted_output += f"```\n{content}\n```"
            
            # Update StreamResponse with formatted result
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = formatted_output
                ctx.deps.stream_output.status_code = 200
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return content
        else:
            error_message = result.get("error", "Unknown error")
            await send_stream_update(ctx, f"Failed to read file: {error_message}")
            
            # Update StreamResponse with error
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = f"## Error\n\nFailed to read file {filename}: {error_message}"
                ctx.deps.stream_output.status_code = 500
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return f"Error: {error_message}"
            
    except Exception as e:
        error_msg = f"Error reading file {filename}: {str(e)}"
        await send_stream_update(ctx, f"File reading failed: {str(e)}")
        logfire.error(error_msg, exc_info=True)
        return error_msg

@coder_agent.tool
async def list_files(ctx: RunContext[CoderAgentDeps]) -> str:
    """
    Lists all files in the persistent Docker environment.
    
    Returns:
        List of files or error message
    """
    try:
        # Send operation description message
        await send_stream_update(ctx, "Listing files in environment")
        
        logfire.info("Listing files in Docker environment")
        
        # Get Docker environment (use python as default)
        from utils.docker_executor import get_environment
        env = get_environment("python")
        
        # Connect to Docker environment
        connect_result = await env.connect()
        if not connect_result.get("success", False):
            error_message = connect_result.get("error", "Unable to connect to Docker environment")
            await send_stream_update(ctx, f"Failed to connect to environment: {error_message}")
            return f"Error: {error_message}"
        
        # List files in Docker environment
        result = await env.list_files()
        
        if result.get("success", False):
            files = result.get("files", [])
            await send_stream_update(ctx, f"Found {len(files)} files")
            
            # Format output for frontend display
            if files:
                formatted_output = "## Files in Environment\n\n"
                formatted_output += "| Filename |\n|----------|\n"
                for filename in files:
                    formatted_output += f"| `{filename}` |\n"
            else:
                formatted_output = "## Files in Environment\n\nNo files found."
            
            # Update StreamResponse with formatted result
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = formatted_output
                ctx.deps.stream_output.status_code = 200
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            if files:
                return f"Files in environment: {', '.join(files)}"
            else:
                return "No files found in environment."
        else:
            error_message = result.get("error", "Unknown error")
            await send_stream_update(ctx, f"Failed to list files: {error_message}")
            
            # Update StreamResponse with error
            if ctx.deps.websocket and ctx.deps.stream_output:
                ctx.deps.stream_output.output = f"## Error\n\nFailed to list files: {error_message}"
                ctx.deps.stream_output.status_code = 500
                await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
            
            return f"Error: {error_message}"
                
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}"
        await send_stream_update(ctx, f"File listing failed: {str(e)}")
        logfire.error(error_msg, exc_info=True)
        return error_msg

@coder_agent.tool
async def execute_file(ctx: RunContext[CoderAgentDeps], filename: str, language: str = None) -> str:
    """
    Executes a file in the persistent Docker environment.
    
    Args:
        filename: Name of the file to execute
        language: Optional programming language (detected from extension if not specified)
        
    Returns:
        Execution results including stdout, stderr, and status
    """
    try:
        # Detect language from filename extension if not provided
        if not language and "." in filename:
            ext = os.path.splitext(filename)[1].lower()
            language_map = {v: k for k, v in LANGUAGE_EXTENSIONS.items()}
            language = language_map.get(ext, None)
        
        if not language:
            return "Error: Could not determine language for execution. Please specify language parameter."
        
        # Send operation description message
        await send_stream_update(ctx, f"Executing file: {filename}")
        
        logfire.info(f"Executing file {filename} in Docker environment with language {language}")
        
        # Get Docker environment for the specific language
        from utils.docker_executor import get_environment
        env = get_environment(language)
        
        # Connect to Docker environment
        connect_result = await env.connect()
        if not connect_result.get("success", False):
            error_message = connect_result.get("error", "Unable to connect to Docker environment")
            await send_stream_update(ctx, f"Failed to connect to environment: {error_message}")
            return f"Error: {error_message}"
        
        # Read file content for display before execution
        file_content = ""
        file_result = await env.read_file(filename)
        if file_result.get("success", False):
            file_content = file_result.get("content", "")
            logfire.debug(f"File content to execute: {file_content}")
        
        # Execute file in Docker environment
        result = await env.execute_code(filename)
        
        # Ensure stdout and stderr are strings
        if "stdout" not in result or result["stdout"] is None:
            result["stdout"] = ""
        if "stderr" not in result or result["stderr"] is None:
            result["stderr"] = ""
            
        # Format the execution results for console output
        output = f"Execution results for {filename}:\n\n"
        
        # Add stdout if available
        if result.get("stdout"):
            output += f"--- Output ---\n{result['stdout']}\n\n"
        else:
            output += "--- No Output ---\n\n"
        
        # Add stderr if there were errors
        if result.get("stderr"):
            output += f"--- Errors ---\n{result['stderr']}\n\n"
        
        # Add execution status
        if result.get("success", False):
            await send_stream_update(ctx, f"File {filename} executed successfully")
            output += "Status: Success\n"
        else:
            await send_stream_update(ctx, f"File {filename} execution failed")
            output += f"Status: Failed (Exit code: {result.get('exit_code', 'unknown')})\n"
        
        # Create a manually crafted formatted output for UI display
        formatted_output = ""
        
        # Always add code section first with proper language syntax highlighting
        formatted_output += f"## File: {filename}\n\n```{language}\n{file_content}\n```\n\n"
        
        # Add execution results section
        formatted_output += "## Output\n\n"
        if result.get("stdout"):
            formatted_output += f"```\n{result['stdout']}\n```\n\n"
        else:
            formatted_output += "*No output captured*\n\n"
        
        # Add errors section if needed
        if result.get("stderr"):
            formatted_output += f"## Errors\n\n```\n{result['stderr']}\n```\n\n"
        
        # Add status section
        if result.get("success", False):
            formatted_output += "## Status\n\n**✅ Execution completed successfully**"
        else:
            exit_code = result.get("exit_code", "unknown")
            formatted_output += f"## Status\n\n**❌ Execution failed** (Exit code: {exit_code})"
        
        # Update StreamResponse with our manually crafted format
        if ctx.deps.websocket and ctx.deps.stream_output:
            ctx.deps.stream_output.output = formatted_output
            ctx.deps.stream_output.source_code = file_content
            ctx.deps.stream_output.status_code = 200 if result.get("success", False) else 500
            ctx.deps.stream_output.metadata = {
                "language": language,
                "filename": filename,
                "success": result.get("success", False),
                "exit_code": result.get("exit_code", "unknown")
            }
            await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
        
        # Log the full output for debugging
        logfire.debug(f"Execution output for {filename}: {output}")
        
        return output
            
    except Exception as e:
        error_msg = f"Error executing file {filename}: {str(e)}"
        await send_stream_update(ctx, f"File execution failed: {str(e)}")
        logfire.error(error_msg, exc_info=True)
        return error_msg