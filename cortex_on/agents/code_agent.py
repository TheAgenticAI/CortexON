# Standard library imports
import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

# Third-party imports
from dotenv import load_dotenv
import logfire
from fastapi import WebSocket
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel

# Local application imports
from utils.ant_client import get_client, get_anthropic_model_instance, get_openai_model_instance, get_openai_client
from utils.stream_response_format import StreamResponse

load_dotenv()


@dataclass
class CoderAgentDeps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None
    model_preference: str = "Anthropic"

# Constants
ALLOWED_COMMANDS = {
    "ls", "dir", "cat", "echo", "python", "pip", 
    "mkdir", "touch", "rm", "cp", "mv"
}

# Message templates - Replace elif ladders with lookup dictionaries
OPERATION_MESSAGES = {
    "ls": lambda cmd, args: "Listing files in directory",
    "dir": lambda cmd, args: "Listing files in directory",
    "cat": lambda cmd, args: (
        f"Creating file {cmd.split('>', 1)[1].strip().split(' ', 1)[0]}" 
        if "<<" in cmd and ">" in cmd
        else f"Reading file {args[1] if len(args) > 1 else 'file'}"
    ),
    "echo": lambda cmd, args: f"Creating file {cmd.split('>', 1)[1].strip()}" if ">" in cmd else "Echo command",
    "python": lambda cmd, args: f"Running Python script {args[1] if len(args) > 1 else 'script'}",
    "pip": lambda cmd, args: (
        f"Installing package(s): {cmd.split('install ', 1)[1]}" 
        if "install " in cmd 
        else "Managing Python packages"
    ),
    "mkdir": lambda cmd, args: f"Creating directory {args[1] if len(args) > 1 else 'directory'}",
    "touch": lambda cmd, args: f"Creating empty file {args[1] if len(args) > 1 else 'file'}",
    "rm": lambda cmd, args: f"Removing {args[1] if len(args) > 1 else 'file'}",
    "cp": lambda cmd, args: f"Copying {args[1]} to {args[2]}" if len(args) >= 3 else "Copying file",
    "mv": lambda cmd, args: f"Moving {args[1]} to {args[2]}" if len(args) >= 3 else "Moving file",
}

EXECUTION_MESSAGES = {
    "python": lambda cmd, args: f"Executing Python script {args[1] if len(args) > 1 else 'script'}",
    "default": lambda cmd, args: "Executing operation"
}

SUCCESS_MESSAGES = {
    "ls": "Files listed successfully",
    "dir": "Files listed successfully",
    "cat": lambda cmd: "File created successfully" if "<<" in cmd else "File read successfully",
    "echo": "File created successfully",
    "python": "Python script executed successfully",
    "pip": lambda cmd: "Package installation completed" if "install" in cmd else "Package operation completed",
    "mkdir": "Directory created successfully",
    "touch": "File created successfully",
    "rm": "File removed successfully",
    "cp": "File copied successfully",
    "mv": "File moved successfully",
    "default": "Operation completed successfully"
}

FAILURE_MESSAGES = {
    "ls": "Failed to list files",
    "dir": "Failed to list files",
    "cat": lambda cmd: "Failed to create file" if "<<" in cmd else "Failed to read file",
    "echo": "Failed to create file",
    "python": "Python script execution failed",
    "pip": lambda cmd: "Package installation failed" if "install" in cmd else "Package operation failed",
    "mkdir": "Failed to create directory",
    "touch": "Failed to create file",
    "rm": "Failed to remove file",
    "cp": "Failed to copy file",
    "mv": "Failed to move file",
    "default": "Operation failed"
}

class CoderResult(BaseModel):
    dependencies: List = Field(
        description="All the packages name that has to be installed before the code execution"
    )
    content: str = Field(description="Response content in the form of code")
    code_description: str = Field(description="Description of the code")

coder_system_message = """You are a helpful AI assistant with coding capabilities. Solve tasks using your coding and language skills.

<critical>
    - You have access to a single shell tool that executes terminal commands and handles file operations.
    - All commands will be executed in a restricted directory for security.
    - Do NOT write code that attempts to access directories outside your working directory.
    - Do NOT provide test run snippets that print unnecessary output.
    - Never use interactive input functions like 'input()' in Python or 'read' in Bash.
    - All code must be non-interactive and should execute completely without user interaction.
    - Use command line arguments, environment variables, or file I/O instead of interactive input.
</critical>

(restricted to your working directory which means you are already in the ./code_files directory)
When solving tasks, use your provided shell tool for all operations:

- execute_shell(command: str) - Execute terminal commands including:
  - File operations: Use 'cat' to read files, 'echo' with redirection (>) to write files
  - Directory operations: 'ls', 'mkdir', etc.
  - Code execution: 'python' for running Python scripts
  - Package management: 'pip install' for dependencies

Allowed commands for execute_shell tool are as follows : ls, dir, cat, echo, python, pip, mkdir, touch, rm, cp, mv  

For Python code, don't use python3, just use python for execution.

Follow this workflow:
1. First, explain your plan and approach to solving the task.
2. Use shell commands to gather information when needed (e.g., 'cat file.py', 'ls').
3. Write code to files using echo with redirection (e.g., 'echo "print('hello')" > script.py').
   - For multi-line files, use the here-document syntax with 'cat' (e.g., 'cat > file.py << 'EOF'\\ncode\\nEOF').
4. Execute the code using 'python script.py'.
5. After each execution, verify the results and fix any errors.
6. Continue this process until the task is complete.

Code guidelines:
- Always specify the script type in code blocks (e.g., ```python, ```sh)
- For files that need to be saved, include "# filename: <filename>" as the first line
- Provide complete, executable code that doesn't require user modification
- Include only one code block per response
- Use print statements appropriately for output, not for debugging

Self-verification:
- After executing code, analyze the output to verify correctness
- If errors occur, fix them and try again with improved code
- If your approach isn't working after multiple attempts, reconsider your strategy

Output explanation guidelines:
- After code execution, structure your explanation according to the CoderResult format
- For each code solution, explain:
  1. Dependencies: List all packages that must be installed before executing the code
  2. Content: The actual code that solves the problem
  3. Code description: A clear explanation of how the code works, its approach, and key components

When presenting results, format your explanation to match the CoderResult class structure:
- First list dependencies (even if empty)
- Then provide the complete code content
- Finally, include a detailed description of the code's functionality and implementation details

Example structure:
Dependencies:
- numpy
- pandas

Content:
[The complete code solution]

Code Description:
This solution implements [approach] to solve [problem]. The code first [key step 1], 
then [key step 2], and finally [produces result]. The implementation handles [edge cases] 
by [specific technique]. Key functions include [function 1] which [purpose],
and [function 2] which [purpose].
"""

# Helper functions
def get_message_from_dict(
    message_dict: Dict[str, Any], 
    command: str, 
    base_command: str
) -> str:
    """Get the appropriate message from a dictionary based on the command."""
    args = command.split()
    
    if base_command in message_dict:
        msg_source = message_dict[base_command]
        if callable(msg_source):
            return msg_source(command, args)
        return msg_source
    
    # Use default message if available, otherwise a generic one
    if "default" in message_dict:
        default_source = message_dict["default"]
        if callable(default_source):
            return default_source(command, args)
        return default_source
    
    return f"Operation: {base_command}"

def get_high_level_operation_message(command: str, base_command: str) -> str:
    """Returns a high-level description of the operation being performed"""
    args = command.split()
    return OPERATION_MESSAGES.get(
        base_command, 
        lambda cmd, args: f"Executing operation: {base_command}"
    )(command, args)

def get_high_level_execution_message(command: str, base_command: str) -> str:
    """Returns a high-level execution message for the command"""
    args = command.split()
    return EXECUTION_MESSAGES.get(
        base_command, 
        EXECUTION_MESSAGES["default"]
    )(command, args)

def get_success_message(command: str, base_command: str) -> str:
    """Returns a success message based on the command type"""
    msg_source = SUCCESS_MESSAGES.get(base_command, SUCCESS_MESSAGES["default"])
    
    if callable(msg_source):
        return msg_source(command)
    
    return msg_source

def get_failure_message(command: str, base_command: str) -> str:
    """Returns a failure message based on the command type"""
    msg_source = FAILURE_MESSAGES.get(base_command, FAILURE_MESSAGES["default"])
    
    if callable(msg_source):
        return msg_source(command)
    
    return msg_source

async def send_stream_update(ctx: RunContext[CoderAgentDeps], message: str) -> None:
    """Helper function to send websocket updates if available"""
    if ctx.deps.websocket and ctx.deps.stream_output:
        ctx.deps.stream_output.steps.append(message)
        await ctx.deps.websocket.send_text(json.dumps(asdict(ctx.deps.stream_output)))
        stream_output_json = json.dumps(asdict(ctx.deps.stream_output))
        logfire.debug("WebSocket message sent: {stream_output_json}", stream_output_json=stream_output_json)



# Initialize the agent

def coder_agent(model_preference: str = "Anthropic"):
    if model_preference == "Anthropic":
        model = get_anthropic_model_instance()
    elif model_preference == "OpenAI":
        model = get_openai_model_instance()
    else:
        raise ValueError(f"Unknown model_preference: {model_preference}")
    print(f"[CODER_INIT] Creating coder agent with model: {model}")
    coder_agent = Agent(
    model=model,
    name="Coder Agent",
    result_type=CoderResult,
    deps_type=CoderAgentDeps,
    system_prompt=coder_system_message
    )    
    return coder_agent

@coder_agent.tool
async def execute_shell(ctx: RunContext[CoderAgentDeps], command: str) -> str:
    """
    Executes a shell command within a restricted directory and returns the output.
    This consolidated tool handles terminal commands and file operations.
    """
    try:
        # Extract base command for security checks and messaging
        base_command = command.split()[0] if command.split() else ""
        
        # Send operation description message
        operation_message = get_high_level_operation_message(command, base_command)
        await send_stream_update(ctx, operation_message)
        
        logfire.info("Executing shell command: {command}", command=command)
        
        # Setup restricted directory
        base_dir = os.path.abspath(os.path.dirname(__file__))
        restricted_dir = os.path.join(base_dir, "code_files")
        os.makedirs(restricted_dir, exist_ok=True)
        
        # Security check
        if base_command not in ALLOWED_COMMANDS:
            await send_stream_update(ctx, "Operation not permitted")
            return f"Error: Command '{base_command}' is not allowed for security reasons."
        
        # Change to restricted directory for execution
        original_dir = os.getcwd()
        os.chdir(restricted_dir)
        
        try:
            # Handle echo with redirection (file writing)
            if ">" in command and base_command == "echo":
                file_path = command.split(">", 1)[1].strip()
                await send_stream_update(ctx, f"Writing content to {file_path}")
                
                # Parse command parts
                parts = command.split(">", 1)
                echo_cmd = parts[0].strip()
                
                # Extract content, removing quotes if present
                content = echo_cmd[5:].strip()
                if (content.startswith('"') and content.endswith('"')) or \
                   (content.startswith("'") and content.endswith("'")):
                    content = content[1:-1]
                
                try:
                    with open(file_path, "w") as file:
                        file.write(content)
                    
                    await send_stream_update(ctx, f"File {file_path} created successfully")
                    return f"Successfully wrote to {file_path}"
                except Exception as e:
                    error_msg = f"Error writing to file: {str(e)}"
                    await send_stream_update(ctx, f"Failed to create file {file_path}")
                    logfire.error(error_msg, exc_info=True)
                    return error_msg
            
            # Handle cat with here-document for multiline file writing
            elif "<<" in command and base_command == "cat":
                cmd_parts = command.split("<<", 1)
                cat_part = cmd_parts[0].strip()
                
                # Extract filename for status message if possible
                file_path = None
                if ">" in cat_part:
                    file_path = cat_part.split(">", 1)[1].strip()
                    await send_stream_update(ctx, f"Creating file {file_path}")
                
                try:
                    # Parse heredoc parts
                    doc_part = cmd_parts[1].strip()
                    
                    # Extract filename
                    if ">" in cat_part:
                        file_path = cat_part.split(">", 1)[1].strip()
                    else:
                        await send_stream_update(ctx, "Invalid file operation")
                        return "Error: Invalid cat command format. Must include redirection."
                    
                    # Parse the heredoc content and delimiter
                    if "\n" in doc_part:
                        delimiter_and_content = doc_part.split("\n", 1)
                        delimiter = delimiter_and_content[0].strip("'").strip('"')
                        content = delimiter_and_content[1]
                        
                        # Find the end delimiter and extract content
                        if f"\n{delimiter}" in content:
                            content = content.split(f"\n{delimiter}")[0]
                            
                            # Write to file
                            with open(file_path, "w") as file:
                                file.write(content)
                            
                            await send_stream_update(ctx, f"File {file_path} created successfully")
                            return f"Successfully wrote multiline content to {file_path}"
                        else:
                            await send_stream_update(ctx, "File content format error")
                            return "Error: End delimiter not found in heredoc"
                    else:
                        await send_stream_update(ctx, "File content format error")
                        return "Error: Invalid heredoc format"
                except Exception as e:
                    error_msg = f"Error processing cat with heredoc: {str(e)}"
                    file_path_str = file_path if file_path else 'file'
                    await send_stream_update(ctx, f"Failed to create file {file_path_str}")
                    logfire.error(error_msg, exc_info=True)
                    return error_msg
            
            # Execute standard commands
            else:
                # Send execution message
                execution_msg = get_high_level_execution_message(command, base_command)
                await send_stream_update(ctx, execution_msg)
                
                # Execute the command using subprocess
                try:
                    args = shlex.split(command)
                    result = subprocess.run(
                        args,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    
                    logfire.info(f"Command executed: {result.args}")
                    
                    # Handle success
                    if result.returncode == 0:
                        success_msg = get_success_message(command, base_command)
                        await send_stream_update(ctx, success_msg)
                        logfire.info(f"Command executed successfully: {result.stdout}")
                        return result.stdout
                    
                    # Handle failure
                    else:
                        files = os.listdir('.')
                        error_msg = f"Command failed with error code {result.returncode}:\n{result.stderr}\n\nFiles in directory: {files}"
                        failure_msg = get_failure_message(command, base_command)
                        await send_stream_update(ctx, failure_msg)
                        return error_msg
                
                except subprocess.TimeoutExpired:
                    await send_stream_update(ctx, "Operation timed out")
                    return "Command execution timed out after 60 seconds"
                
                except Exception as e:
                    error_msg = f"Error executing command: {str(e)}"
                    await send_stream_update(ctx, "Operation failed")
                    logfire.error(error_msg, exc_info=True)
                    return error_msg
        
        finally:
            # Always return to the original directory
            os.chdir(original_dir)
            
    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        await send_stream_update(ctx, "Operation failed")
        logfire.error(error_msg, exc_info=True)
        return error_msg