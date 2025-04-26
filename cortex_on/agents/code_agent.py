# Standard library imports
import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

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

load_dotenv()


@dataclass
class CoderAgentDeps:
    websocket: Optional[WebSocket] = None
    stream_output: Optional[StreamResponse] = None

# Constants - Expanded to support multiple languages
ALLOWED_COMMANDS = {
    # File system commands
    "ls", "dir", "cat", "echo", "mkdir", "touch", "rm", "cp", "mv",
    
    # Language interpreters/compilers
    "python", "python3", "pip", "node", "npm", "java", "javac", 
    "gcc", "g++", "clang", "clang++", "go", "rustc", "cargo",
    "ruby", "perl", "php", "dotnet", "csc", "swift",
    
    # TypeScript specific commands
    "tsc", "npx", "ts-node",
    
    # Build tools
    "make", "cmake", "gradle", "maven", "mvn",
    
    # Runtime utilities
    "sh", "bash", "zsh", "powershell", "pwsh"
}

# Language-specific file extensions
LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "python3": ".py",
    "javascript": ".js",
    "node": ".js",
    "typescript": ".ts",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "c++": ".cpp",
    "csharp": ".cs",
    "c#": ".cs",
    "go": ".go",
    "golang": ".go",
    "rust": ".rs",
    "ruby": ".rb",
    "perl": ".pl",
    "php": ".php",
    "swift": ".swift",
    "kotlin": ".kt",
    "scala": ".scala",
    "shell": ".sh",
    "bash": ".sh",
    "powershell": ".ps1",
    "pwsh": ".ps1",
    "r": ".r",
    "html": ".html",
    "css": ".css",
    "sql": ".sql",
}

# Language execution commands
LANGUAGE_EXECUTION_COMMANDS = {
    "python": "python",
    "python3": "python3",
    "javascript": "node",
    "node": "node",
    "typescript": lambda file: f"npx ts-node {file}",  # Use npx ts-node for TypeScript
    "java": lambda file: f"java {os.path.splitext(file)[0]}", # Remove .java extension
    "c": lambda file: f"gcc {file} -o {os.path.splitext(file)[0]} && {os.path.splitext(file)[0]}",
    "cpp": lambda file: f"g++ {file} -o {os.path.splitext(file)[0]} && {os.path.splitext(file)[0]}",
    "c++": lambda file: f"g++ {file} -o {os.path.splitext(file)[0]} && {os.path.splitext(file)[0]}",
    "csharp": "dotnet run",
    "c#": "dotnet run",
    "go": "go run",
    "golang": "go run",
    "rust": lambda file: f"rustc {file} -o {os.path.splitext(file)[0]} && {os.path.splitext(file)[0]}",
    "ruby": "ruby",
    "perl": "perl",
    "php": "php",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "shell": "sh",
    "bash": "bash",
    "powershell": "pwsh",
    "pwsh": "pwsh",
    "r": "Rscript",
}

# Package managers for different languages
PACKAGE_MANAGERS = {
    "python": {"install": "pip install", "uninstall": "pip uninstall", "list": "pip list"},
    "python3": {"install": "pip3 install", "uninstall": "pip3 uninstall", "list": "pip3 list"},
    "javascript": {"install": "npm install", "uninstall": "npm uninstall", "list": "npm list"},
    "node": {"install": "npm install", "uninstall": "npm uninstall", "list": "npm list"},
    "typescript": {"install": "npm install", "uninstall": "npm uninstall", "list": "npm list"},
    "java": {"install": "mvn install", "uninstall": "mvn uninstall", "list": "mvn dependency:list"},
    "rust": {"install": "cargo add", "uninstall": "cargo remove", "list": "cargo tree"},
    "ruby": {"install": "gem install", "uninstall": "gem uninstall", "list": "gem list"},
    "go": {"install": "go get", "uninstall": "go clean -i", "list": "go list -m all"},
    "php": {"install": "composer require", "uninstall": "composer remove", "list": "composer show"},
    "csharp": {"install": "dotnet add package", "uninstall": "dotnet remove package", "list": "dotnet list package"},
    "c#": {"install": "dotnet add package", "uninstall": "dotnet remove package", "list": "dotnet list package"},
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
    "mkdir": lambda cmd, args: f"Creating directory {args[1] if len(args) > 1 else 'directory'}",
    "touch": lambda cmd, args: f"Creating empty file {args[1] if len(args) > 1 else 'file'}",
    "rm": lambda cmd, args: f"Removing {args[1] if len(args) > 1 else 'file'}",
    "cp": lambda cmd, args: f"Copying {args[1]} to {args[2]}" if len(args) >= 3 else "Copying file",
    "mv": lambda cmd, args: f"Moving {args[1]} to {args[2]}" if len(args) >= 3 else "Moving file",
    
    "tsc": lambda cmd, args: f"Compiling TypeScript {args[1] if len(args) > 1 else 'program'}",
    "ts-node": lambda cmd, args: f"Running TypeScript {args[1] if len(args) > 1 else 'program'}",
    "npx": lambda cmd, args: f"Executing NPX command: {' '.join(args[1:]) if len(args) > 1 else 'command'}",

    # Python specific
    "python": lambda cmd, args: f"Running Python script {args[1] if len(args) > 1 else 'script'}",
    "python3": lambda cmd, args: f"Running Python script {args[1] if len(args) > 1 else 'script'}",
    "pip": lambda cmd, args: (
        f"Installing Python package(s): {cmd.split('install ', 1)[1]}" 
        if "install " in cmd 
        else "Managing Python packages"
    ),
    
    # JavaScript/Node.js
    "node": lambda cmd, args: f"Running Node.js script {args[1] if len(args) > 1 else 'script'}",
    "npm": lambda cmd, args: (
        f"Installing Node.js package(s): {cmd.split('install ', 1)[1]}" 
        if "install " in cmd 
        else "Managing Node.js packages"
    ),
    
    # Java
    "java": lambda cmd, args: f"Running Java program {args[1] if len(args) > 1 else 'program'}",
    "javac": lambda cmd, args: f"Compiling Java files {' '.join(args[1:]) if len(args) > 1 else ''}",
    
    # C/C++
    "gcc": lambda cmd, args: f"Compiling C program {args[1] if len(args) > 1 else 'program'}",
    "g++": lambda cmd, args: f"Compiling C++ program {args[1] if len(args) > 1 else 'program'}",
    "clang": lambda cmd, args: f"Compiling C program with Clang {args[1] if len(args) > 1 else 'program'}",
    "clang++": lambda cmd, args: f"Compiling C++ program with Clang {args[1] if len(args) > 1 else 'program'}",
    
    # Go
    "go": lambda cmd, args: (
        f"Running Go program {args[1] if len(args) > 1 else 'program'}" 
        if args[0] == "run" 
        else f"Managing Go {args[0]} operation"
    ),
    
    # Rust
    "rustc": lambda cmd, args: f"Compiling Rust program {args[1] if len(args) > 1 else 'program'}",
    "cargo": lambda cmd, args: f"Managing Rust project with Cargo: {args[1] if len(args) > 1 else 'operation'}",
    
    # Ruby
    "ruby": lambda cmd, args: f"Running Ruby script {args[1] if len(args) > 1 else 'script'}",
    
    # Other languages
    "perl": lambda cmd, args: f"Running Perl script {args[1] if len(args) > 1 else 'script'}",
    "php": lambda cmd, args: f"Running PHP script {args[1] if len(args) > 1 else 'script'}",
    "dotnet": lambda cmd, args: f"Running .NET command: {args[1] if len(args) > 1 else 'command'}",
    "csc": lambda cmd, args: f"Compiling C# program {args[1] if len(args) > 1 else 'program'}",
    "swift": lambda cmd, args: f"Running Swift program {args[1] if len(args) > 1 else 'program'}",
    
    # Build tools
    "make": lambda cmd, args: f"Building with Make {args[1] if len(args) > 1 else ''}",
    "cmake": lambda cmd, args: f"Configuring with CMake {args[1] if len(args) > 1 else ''}",
    "gradle": lambda cmd, args: f"Building with Gradle {args[1] if len(args) > 1 else ''}",
    "maven": lambda cmd, args: f"Building with Maven {args[1] if len(args) > 1 else ''}",
    "mvn": lambda cmd, args: f"Building with Maven {args[1] if len(args) > 1 else ''}",
    
    # Shell commands
    "sh": lambda cmd, args: f"Running shell script {args[1] if len(args) > 1 else 'script'}",
    "bash": lambda cmd, args: f"Running Bash script {args[1] if len(args) > 1 else 'script'}",
    "zsh": lambda cmd, args: f"Running Zsh script {args[1] if len(args) > 1 else 'script'}",
    "powershell": lambda cmd, args: f"Running PowerShell script {args[1] if len(args) > 1 else 'script'}",
    "pwsh": lambda cmd, args: f"Running PowerShell script {args[1] if len(args) > 1 else 'script'}",
}

EXECUTION_MESSAGES = {
    "python": lambda cmd, args: f"Executing Python script {args[1] if len(args) > 1 else 'script'}",
    "python3": lambda cmd, args: f"Executing Python script {args[1] if len(args) > 1 else 'script'}",
    "node": lambda cmd, args: f"Executing Node.js script {args[1] if len(args) > 1 else 'script'}",
    "java": lambda cmd, args: f"Executing Java program {args[1] if len(args) > 1 else 'program'}",
    "default": lambda cmd, args: "Executing operation"
}

SUCCESS_MESSAGES = {
    # File operations
    "ls": "Files listed successfully",
    "dir": "Files listed successfully",
    "cat": lambda cmd: "File created successfully" if "<<" in cmd else "File read successfully",
    "echo": lambda cmd: "File created successfully" if ">" in cmd else "Echo executed successfully",
    "mkdir": "Directory created successfully",
    "touch": "File created successfully",
    "rm": "File removed successfully",
    "cp": "File copied successfully",
    "mv": "File moved successfully",
    
    "tsc": "TypeScript compilation completed successfully",
    "ts-node": "TypeScript executed successfully",
    "npx": lambda cmd: "TypeScript executed successfully" if "ts-node" in cmd else "NPX command executed successfully",

    # Python
    "python": "Python script executed successfully",
    "python3": "Python script executed successfully",
    "pip": lambda cmd: "Package installation completed" if "install" in cmd else "Package operation completed",
    
    # JavaScript/Node.js
    "node": "Node.js script executed successfully",
    "npm": lambda cmd: "Node.js package operation completed successfully",
    
    # Java
    "java": "Java program executed successfully",
    "javac": "Java program compiled successfully",
    
    # C/C++
    "gcc": "C program compiled successfully",
    "g++": "C++ program compiled successfully",
    "clang": "C program compiled successfully with Clang",
    "clang++": "C++ program compiled successfully with Clang",
    
    # Go
    "go": lambda cmd: "Go program executed successfully" if "run" in cmd else "Go operation completed successfully",
    
    # Rust
    "rustc": "Rust program compiled successfully",
    "cargo": "Cargo operation completed successfully",
    
    # Other languages
    "ruby": "Ruby script executed successfully",
    "perl": "Perl script executed successfully",
    "php": "PHP script executed successfully",
    "dotnet": "Dotnet operation completed successfully",
    "csc": "C# program compiled successfully",
    "swift": "Swift program executed successfully",
    
    # Build tools
    "make": "Make build completed successfully",
    "cmake": "CMake configuration completed successfully",
    "gradle": "Gradle build completed successfully",
    "maven": "Maven build completed successfully",
    "mvn": "Maven build completed successfully",
    
    # Shell scripts
    "sh": "Shell script executed successfully",
    "bash": "Bash script executed successfully",
    "zsh": "Zsh script executed successfully",
    "powershell": "PowerShell script executed successfully",
    "pwsh": "PowerShell script executed successfully",
    
    "default": "Operation completed successfully"
}

FAILURE_MESSAGES = {
    # File operations
    "ls": "Failed to list files",
    "dir": "Failed to list files",
    "cat": lambda cmd: "Failed to create file" if "<<" in cmd else "Failed to read file",
    "echo": lambda cmd: "Failed to create file" if ">" in cmd else "Echo command failed",
    "mkdir": "Failed to create directory",
    "touch": "Failed to create file",
    "rm": "Failed to remove file",
    "cp": "Failed to copy file",
    "mv": "Failed to move file",
    "tsc": "TypeScript compilation failed",
    "ts-node": "TypeScript execution failed",
    "npx": lambda cmd: "TypeScript execution failed" if "ts-node" in cmd else "NPX command execution failed",

    # Python
    "python": "Python script execution failed",
    "python3": "Python script execution failed",
    "pip": lambda cmd: "Package installation failed" if "install" in cmd else "Package operation failed",
    
    # JavaScript/Node.js
    "node": "Node.js script execution failed",
    "npm": lambda cmd: "Node.js package operation failed",
    
    # Java
    "java": "Java program execution failed",
    "javac": "Java program compilation failed",
    
    # C/C++
    "gcc": "C program compilation failed",
    "g++": "C++ program compilation failed",
    "clang": "C program compilation failed with Clang",
    "clang++": "C++ program compilation failed with Clang",
    
    # Go
    "go": lambda cmd: "Go program execution failed" if "run" in cmd else "Go operation failed",
    
    # Rust
    "rustc": "Rust program compilation failed",
    "cargo": "Cargo operation failed",
    
    # Other languages
    "ruby": "Ruby script execution failed",
    "perl": "Perl script execution failed",
    "php": "PHP script execution failed",
    "dotnet": "Dotnet operation failed",
    "csc": "C# program compilation failed",
    "swift": "Swift program execution failed",
    
    # Build tools
    "make": "Make build failed",
    "cmake": "CMake configuration failed",
    "gradle": "Gradle build failed",
    "maven": "Maven build failed",
    "mvn": "Maven build failed",
    
    # Shell scripts
    "sh": "Shell script execution failed",
    "bash": "Bash script execution failed",
    "zsh": "Zsh script execution failed",
    "powershell": "PowerShell script execution failed",
    "pwsh": "PowerShell script execution failed",
    
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
  - Code execution: 'python', 'node', 'java', 'gcc', etc. for running programs in different languages
  - Package management: 'pip install', 'npm install', 'cargo add', etc. for dependencies

Allowed commands for execute_shell tool include: ls, dir, cat, echo, python, python3, pip, node, npm, java, javac, gcc, g++, clang, clang++, go, rustc, cargo, ruby, perl, php, dotnet, csc, swift, make, cmake, gradle, maven, mvn, sh, bash, zsh, powershell, pwsh, mkdir, touch, rm, cp, mv

Different programming languages have different ways to handle files and execution:

1. For Python code:
   - Create files with: echo "print('hello')" > script.py
   - For multi-line files: cat > file.py << 'EOF'\\ncode\\nEOF
   - Execute with: python script.py or python3 script.py
   - Install packages with: pip install package_name

2. For JavaScript/Node.js:
   - Create files with: echo "console.log('hello')" > script.js
   - Execute with: node script.js
   - Install packages with: npm install package_name

3. For Java:
   - Create files with: echo "public class Main { public static void main(String[] args) { System.out.println(\"Hello\"); } }" > Main.java
   - Compile with: javac Main.java
   - Execute with: java Main

4. For C/C++:
   - Create files with: echo "#include <stdio.h>\\nint main() { printf(\"Hello\\n\"); return 0; }" > program.c
   - Compile and run: gcc program.c -o program && ./program (for C)
   - Or: g++ program.cpp -o program && ./program (for C++)

5. For Go:
   - Create files with: echo "package main\\nimport \"fmt\"\\nfunc main() { fmt.Println(\"Hello\") }" > main.go
   - Execute with: go run main.go

6. For Rust:
   - Create files with: echo "fn main() { println!(\"Hello\"); }" > main.rs
   - Compile and run: rustc main.rs -o main && ./main
   - Or use Cargo for projects

7. For Ruby:
   - Create files with: echo "puts 'Hello'" > script.rb
   - Execute with: ruby script.rb

8. For shell scripts:
   - Create files with: echo "echo 'Hello'" > script.sh
   - Execute with: bash script.sh or sh script.sh

Follow this workflow:
1. First, explain your plan and approach to solving the task.
2. Use shell commands to gather information when needed (e.g., 'cat file.py', 'ls').
3. Write code to files using echo with redirection or cat with here-documents.
4. Execute the code using the appropriate command for the language.
5. After each execution, verify the results and fix any errors.
6. Continue this process until the task is complete.

Code guidelines:
- Always specify the script type in code blocks (e.g., ```python, ```java, ```javascript)
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

def detect_language_from_extension(filename: str) -> Tuple[str, str]:
    """Determine the language and execution command based on file extension"""
    ext = os.path.splitext(filename)[1].lower()
    
    extensions_to_language = {
        ".py": "python",
        ".js": "node",
        ".ts": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".pl": "perl",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".ps1": "powershell",
        ".r": "r"
    }
    
    language = extensions_to_language.get(ext, "unknown")
    
    # Get execution command for this language
    execution_cmd = LANGUAGE_EXECUTION_COMMANDS.get(language, None)
    
    if callable(execution_cmd):
        cmd = execution_cmd(filename)
    elif execution_cmd:
        cmd = f"{execution_cmd} {filename}"
    else:
        cmd = f"echo 'Unsupported file type: {ext}'"
    
    return language, cmd

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
                
                # Special handling for language-specific execution
                # For compile+run commands like gcc, g++, rustc, etc.
                
                # Execute the command using subprocess
                try:
                    args = shlex.split(command)
                    
                    # Check if this is a language execution command that might need special handling
                    if len(args) > 1 and any(ext in args[1] for ext in LANGUAGE_EXTENSIONS.values()):
                        # This might be a code execution command, detect the language
                        language, execution_cmd = detect_language_from_extension(args[1])
                        
                        # If this is a compiled language that needs a separate compile+run step
                        if base_command in ["gcc", "g++", "clang", "clang++", "javac", "rustc"]:
                            # For these commands, we need to compile first, then run in two steps
                            compile_result = subprocess.run(
                                args,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=60,
                            )
                            
                            if compile_result.returncode != 0:
                                compile_error = f"Compilation failed: {compile_result.stderr}"
                                await send_stream_update(ctx, f"Compilation failed")
                                return compile_error
                            
                            # Now run the compiled program if compilation was successful
                            filename = args[1]
                            _, executable_cmd = detect_language_from_extension(filename)
                            
                            # Execute the compiled program
                            run_args = shlex.split(executable_cmd)
                            result = subprocess.run(
                                run_args,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=60,
                            )
                            
                            combined_output = f"Compilation output:\n{compile_result.stdout}\n\nExecution output:\n{result.stdout}"
                            
                            if result.returncode == 0:
                                success_msg = get_success_message(command, base_command)
                                await send_stream_update(ctx, success_msg)
                                logfire.info(f"Command executed successfully")
                                return combined_output
                            else:
                                error_msg = f"Execution failed with error code {result.returncode}:\n{result.stderr}"
                                failure_msg = get_failure_message(command, base_command)
                                await send_stream_update(ctx, failure_msg)
                                return combined_output + f"\n\nError: {error_msg}"
                    
                    # For direct execution commands (python, node, etc.)
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