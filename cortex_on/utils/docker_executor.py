import os
import uuid
import logging
import tempfile
import time
import json
import io
import tarfile
import docker
from typing import Dict, Optional, List, Union, Tuple, Any

# Configure logger with more detailed format
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Language configurations
SUPPORTED_LANGUAGES = {
    "python": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".py",
        "execute_cmd": lambda filename: f"python {filename}",
        "work_dir": "/app/python"
    },
    "java": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".java",
        "execute_cmd": lambda filename: f"javac {filename} && java -cp . {os.path.splitext(os.path.basename(filename))[0]}",
        "work_dir": "/app/java"
    },
    "cpp": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".cpp",
        "execute_cmd": lambda filename: f"g++ {filename} -o /tmp/program",
        "work_dir": "/app/cpp"
    },
    "javascript": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".js",
        "execute_cmd": lambda filename: f"node {filename}",
        "work_dir": "/app/javascript"
    },
    "typescript": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".ts",
        "execute_cmd": lambda filename: f"tsc {filename} --outFile /tmp/out.js && node /tmp/out.js",
        "work_dir": "/app/typescript"
    },
    "ruby": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".rb",
        "execute_cmd": lambda filename: f"ruby {filename}",
        "work_dir": "/app/ruby"
    },
    "go": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".go",
        "execute_cmd": lambda filename: f"cd {os.path.dirname(filename) or '.'} && go run {os.path.basename(filename)}",
        "work_dir": "/app/go"
    },
    "rust": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".rs",
        "execute_cmd": lambda filename: f"rustc {filename} -o /tmp/program && /tmp/program",
        "work_dir": "/app/rust"
    },
    "php": {
        "container_name": "cortexon_multi_env",
        "file_extension": ".php",
        "execute_cmd": lambda filename: f"php {filename}",
        "work_dir": "/app/php"
    }
}

# Language aliases mapping
LANGUAGE_ALIASES = {
    "python3": "python",
    "py": "python",
    "c++": "cpp",
    "node": "javascript",
    "nodejs": "javascript",
    "js": "javascript",
    "rb": "ruby",
    "golang": "go",
    "rs": "rust",
    "ts": "typescript",
    "php": "php",
    "java": "java"
}

class DockerEnvironment:
    """
    Connects to a persistent Docker container for code execution.
    These containers should be defined in the docker-compose.yml.
    """
    def __init__(
        self, 
        language: str = "python", 
        work_dir: str = None
    ):
        """
        Initialize a connection to a Docker environment
        
        Args:
            language: The primary programming language for this environment
            work_dir: Working directory in the container (optional, will use language-specific dir if not provided)
        """
        self.client = docker.from_env()
        self.language = language
        self.container_name = SUPPORTED_LANGUAGES[language]["container_name"]
        self.work_dir = work_dir if work_dir else SUPPORTED_LANGUAGES[language]["work_dir"]
        self.files = {}  # Keep track of files in the container
        self.active = False
        self.container = None
        
        logger.info(f"Initialized Docker environment for {self.language}")
        
    async def connect(self) -> Dict[str, Any]:
        """
        Connect to the persistent Docker container for this environment
        
        Returns:
            Status dictionary with success/error information
        """
        if self.active:
            logger.info(f"Already connected to container {self.container_name}")
            return {"success": True, "message": "Already connected"}
        
        try:
            logger.info(f"Connecting to container {self.container_name}")
            
            # Get container by name
            self.container = self.client.containers.get(self.container_name)
            
            # Check if container is running
            if self.container.status != "running":
                logger.info(f"Container {self.container_name} is not running, attempting to start")
                self.container.start()
            
            self.active = True
            logger.info(f"Successfully connected to container {self.container_name}")
            
            # Create workspace directory if it doesn't exist
            self._exec_command(f"mkdir -p {self.work_dir}")
            
            # Activate the appropriate language environment
            self._activate_language_environment()
            
            return {
                "success": True, 
                "container_id": self.container.id,
                "message": f"Successfully connected to container {self.container_name} and activated {self.language} environment"
            }
            
        except docker.errors.NotFound:
            error_msg = f"Container {self.container_name} not found. Make sure it's defined in docker-compose.yml"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            error_msg = f"Failed to connect to container: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    def _activate_language_environment(self):
        """
        Activate the appropriate language environment in the container
        """
        try:
            logger.info(f"Activating {self.language} environment in container")
            
            # Use the use_env script to activate the environment
            exit_code, stdout, stderr = self._exec_command(f"use_env {self.language}")
            
            if exit_code != 0:
                logger.error(f"Failed to activate {self.language} environment: {stderr}")
            else:
                logger.info(f"Successfully activated {self.language} environment: {stdout}")
                
        except Exception as e:
            logger.error(f"Error activating {self.language} environment: {str(e)}")
    
    def _exec_command(self, cmd: str) -> Tuple[int, str, str]:
        """
        Execute a command in the container
        
        Args:
            cmd: Command to execute
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.active:
            logger.error("Cannot execute command: Not connected to container")
            return (1, "", "Not connected to container")
        
        try:
            # Always wrap commands in 'bash -c' but ensure they're simple
            shell_cmd = ['bash', '-c', cmd]
            
            logger.info(f"Running command: {cmd}")
            
            # Execute command in container with TTY disabled for proper output capture
            exec_result = self.container.exec_run(
                cmd=shell_cmd,
                workdir=self.work_dir,
                demux=True,  # Split stdout and stderr
                tty=False,   # Disable TTY to ensure proper output capture
                stream=False # Don't stream output
            )
            
            exit_code = exec_result.exit_code
            
            # Process stdout and stderr
            stdout, stderr = "", ""
            if isinstance(exec_result.output, tuple) and len(exec_result.output) == 2:
                stdout_bytes, stderr_bytes = exec_result.output
                if stdout_bytes:
                    stdout = stdout_bytes.decode('utf-8', errors='replace')
                if stderr_bytes:
                    stderr = stderr_bytes.decode('utf-8', errors='replace')
            
            # Log the output
            logger.info(f"Command exit code: {exit_code}")
            logger.info(f"Command stdout: [{stdout}]")
            logger.info(f"Command stderr: [{stderr}]")
            
            # Try alternate output capture method if output is empty
            if not stdout and not stderr and exit_code == 0:
                logger.info("No output captured with primary method, trying alternate method")
                # Use output redirection to a file and then read it
                output_file = f"/tmp/output_{int(time.time())}.txt"
                
                # Run the command and redirect output to file, then read file
                alt_cmd1 = f"{cmd} > {output_file} 2>> {output_file}"
                self.container.exec_run(
                    cmd=['bash', '-c', alt_cmd1],
                    workdir=self.work_dir
                )
                
                # Read the output file
                alt_cmd2 = f"cat {output_file}"
                alt_result = self.container.exec_run(
                    cmd=['bash', '-c', alt_cmd2],
                    workdir=self.work_dir
                )
                
                if alt_result.exit_code == 0 and alt_result.output:
                    stdout = alt_result.output.decode('utf-8', errors='replace')
                    logger.info(f"Alternate method stdout: [{stdout}]")
                
                # Clean up
                alt_cmd3 = f"rm -f {output_file}"
                self.container.exec_run(
                    cmd=['bash', '-c', alt_cmd3],
                    workdir=self.work_dir
                )
            
            return (exit_code, stdout, stderr)
            
        except Exception as e:
            error_msg = f"Command execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (1, "", error_msg)
    
    async def write_file(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Write content to a file in the container
        
        Args:
            filename: Name of the file to create/write
            content: Content to write to the file
            
        Returns:
            Status dictionary with success/error information
        """
        if not self.active:
            await self.connect()
        
        try:
            # Create a temporary directory for the file
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write content to a local file
                temp_file_path = os.path.join(temp_dir, os.path.basename(filename))
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Read the file as binary
                with open(temp_file_path, 'rb') as f:
                    data = f.read()
                
                # Create archive containing the file
                import tarfile
                import io
                
                # Create tar archive in memory
                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                    tarinfo = tarfile.TarInfo(name=os.path.basename(filename))
                    tarinfo.size = len(data)
                    tar.addfile(tarinfo, io.BytesIO(data))
                
                tar_stream.seek(0)
                tar_data = tar_stream.read()
                
                # Create any necessary directories in the container
                dir_name = os.path.dirname(filename)
                if dir_name:
                    # Create directory if needed
                    logger.info(f"Creating directory in container: {os.path.join(self.work_dir, dir_name)}")
                    self._exec_command(f"mkdir -p {os.path.join(self.work_dir, dir_name)}")
                
                # Path where to extract the archive
                extract_path = self.work_dir
                if dir_name:
                    extract_path = os.path.join(self.work_dir, dir_name)
                
                logger.info(f"Extracting file to container path: {extract_path}")
                
                # Copy the tar archive to the container
                result = self.container.put_archive(path=extract_path, data=tar_data)
                
                if not result:
                    error_msg = "Failed to copy file to container"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            
            # Verify the file was created - construct full path for verification
            full_path = os.path.join(self.work_dir, filename)
            logger.info(f"Verifying file existence at: {full_path}")
            check_cmd = f"test -f '{full_path}' && echo 'success' || echo 'not found'"
            exit_code, stdout, stderr = self._exec_command(check_cmd)
            
            # List directory contents for debugging
            ls_cmd = f"ls -la {os.path.dirname(full_path) or '.'}"
            self._exec_command(ls_cmd)
            
            if "not found" in stdout:
                error_msg = f"File verification failed: {full_path} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Add to files dictionary
            self.files[filename] = {
                "path": full_path,
                "size": len(content),
                "last_modified": time.time()
            }
            
            logger.info(f"File {filename} written to container {self.container_name}")
            return {
                "success": True,
                "filename": filename, 
                "size": len(content),
                "message": f"File {filename} created successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to write file {filename}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def read_file(self, filename: str) -> Dict[str, Any]:
        """
        Read content from a file in the container
        
        Args:
            filename: Name of the file to read
            
        Returns:
            Dictionary with file content and success status
        """
        if not self.active:
            return {"success": False, "error": "Not connected to container"}
        
        try:
            # Ensure we're in the correct language environment
            self._activate_language_environment()
            
            # Check if file exists using a shell-compatible command
            exit_code, stdout, stderr = self._exec_command(f"test -f {filename} && echo 'exists' || echo 'not_exists'")
            
            if "not_exists" in stdout:
                return {"success": False, "error": f"File {filename} not found"}
            
            # Read file content
            exit_code, stdout, stderr = self._exec_command(f"cat {filename}")
            
            if exit_code != 0:
                return {"success": False, "error": f"Failed to read file: {stderr}"}
            
            return {
                "success": True,
                "filename": filename,
                "content": stdout,
                "size": len(stdout)
            }
            
        except Exception as e:
            error_msg = f"Failed to read file {filename}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def delete_file(self, filename: str) -> Dict[str, Any]:
        """
        Delete a file from the container
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            Status dictionary with success/error information
        """
        if not self.active:
            return {"success": False, "error": "Not connected to container"}
        
        try:
            # Ensure we're in the correct language environment
            self._activate_language_environment()
            
            # Delete the file
            exit_code, stdout, stderr = self._exec_command(f"rm -f {filename}")
            
            if exit_code != 0:
                return {"success": False, "error": f"Failed to delete file: {stderr}"}
            
            # Remove from files dictionary
            if filename in self.files:
                del self.files[filename]
                
            return {
                "success": True,
                "filename": filename,
                "message": f"File {filename} deleted successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to delete file {filename}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def list_files(self) -> Dict[str, Any]:
        """
        List all files in the container's working directory
        
        Returns:
            Dictionary with file listing and success status
        """
        if not self.active:
            return {"success": False, "error": "Not connected to container"}
        
        try:
            # Ensure we're in the correct language environment
            self._activate_language_environment()
            
            # List files - Using a simpler find command that works correctly
            exit_code, stdout, stderr = self._exec_command(f"find '{self.work_dir}' -type f -not -path '*/\\.*'")
            
            if exit_code != 0:
                return {"success": False, "error": f"Failed to list files: {stderr}"}
            
            # Process file list
            file_list = []
            if stdout:
                # Get more detailed info for each file
                for file_path in stdout.strip().split('\n'):
                    if file_path:
                        # Get file information
                        name = os.path.basename(file_path)
                        file_list.append(name)
                        
                        # Update files dictionary
                        if name not in self.files:
                            self.files[name] = {
                                "path": file_path,
                                "last_modified": time.time()
                            }
            
            return {
                "success": True,
                "files": file_list,
                "count": len(file_list)
            }
            
        except Exception as e:
            error_msg = f"Failed to list files: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def execute_code(self, filename: str) -> Dict[str, Any]:
        """
        Execute a file in the container
        
        Args:
            filename: Name of the file to execute
            
        Returns:
            Dictionary with execution results
        """
        if not self.active:
            await self.connect()
        
        try:
            # Check if file exists using simple test command
            exit_code, stdout, stderr = self._exec_command(f"test -f {filename}")
            if exit_code != 0:
                return {"success": False, "error": f"File {filename} not found"}
            
            # Ensure the correct language environment is activated
            self._activate_language_environment()
            
            # Get execution command for this language
            exec_cmd_generator = SUPPORTED_LANGUAGES[self.language]["execute_cmd"]
            if not exec_cmd_generator:
                return {"success": False, "error": f"No execution command defined for {self.language}"}
            
            # Special handling for C++ to separate compile and run steps
            if self.language == "cpp":
                logger.info(f"Compiling C++ file: {filename}")
                
                # First compile
                compile_cmd = exec_cmd_generator(filename)
                compile_exit_code, compile_stdout, compile_stderr = self._exec_command(compile_cmd)
                
                # If compilation failed, return the error
                if compile_exit_code != 0:
                    return {
                        "execution_id": str(uuid.uuid4()),
                        "language": self.language,
                        "filename": filename,
                        "stdout": compile_stdout,
                        "stderr": compile_stderr,
                        "exit_code": compile_exit_code,
                        "success": False
                    }
                
                logger.info(f"C++ compilation successful, running: /tmp/program")
                
                # Then run the compiled program
                run_cmd = "/tmp/program"
                exit_code, stdout, stderr = self._exec_command(run_cmd)
            else:
                # For other languages, execute directly
                if callable(exec_cmd_generator):
                    exec_cmd = exec_cmd_generator(filename)
                else:
                    exec_cmd = f"{exec_cmd_generator} {filename}"
                
                logger.info(f"Executing {filename} with command: {exec_cmd}")
                
                # Execute command
                exit_code, stdout, stderr = self._exec_command(exec_cmd)
            
            # If no output, try with explicit redirection to a file then read it
            if exit_code == 0 and not stdout and not stderr:
                logger.info("No output from direct execution, trying with file redirection")
                output_file = f"/tmp/output_{uuid.uuid4().hex}.txt"
                
                if self.language == "cpp":
                    # For C++, redirect the compiled program output
                    redirect_cmd = f"/tmp/program > {output_file} 2>> {output_file}"
                    self._exec_command(redirect_cmd)
                else:
                    # For other languages
                    if callable(exec_cmd_generator):
                        redirect_cmd = f"{exec_cmd} > {output_file} 2>> {output_file}"
                        self._exec_command(redirect_cmd)
                
                # Read the output file
                cat_cmd = f"cat {output_file}"
                cat_result = self._exec_command(cat_cmd)
                if cat_result[0] == 0 and cat_result[1]:
                    stdout = cat_result[1]
                
                # Clean up
                rm_cmd = f"rm -f {output_file}"
                self._exec_command(rm_cmd)
            
            # Return execution results
            execution_id = str(uuid.uuid4())
            result = {
                "execution_id": execution_id,
                "language": self.language,
                "filename": filename,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": exit_code == 0
            }
            
            logger.info(f"Execution completed with status: {result['success']}")
            return result
            
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def disconnect(self) -> Dict[str, Any]:
        """
        Disconnect from the container (does not stop it)
            
        Returns:
            Status dictionary
        """
        if not self.active:
            return {"success": True, "message": "Already disconnected"}
        
        try:
            self.active = False
            self.container = None
            logger.info(f"Disconnected from container {self.container_name}")
            
            return {
                "success": True,
                "message": f"Disconnected from container {self.container_name}"
            }
            
        except Exception as e:
            error_msg = f"Failed to disconnect: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

# Global registry to track active Docker environments - indexed by language
docker_environments = {}

def get_environment(language: str) -> DockerEnvironment:
    """
    Get an existing Docker environment or create a new connection
    
    Args:
        language: Programming language for this environment
        
    Returns:
        DockerEnvironment instance
    """
    global docker_environments
    
    # Normalize language name
    language = language.lower().strip()
    
    # Map language aliases to standard names
    language = LANGUAGE_ALIASES.get(language, language)
    
    # Check if language is supported
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {language}, falling back to Python")
        language = "python"
    
    # Get or create environment for this language
    if language in docker_environments:
        env = docker_environments[language]
        logger.info(f"Reusing existing environment for {language}")
        return env
    
    logger.info(f"Creating new environment for language: {language}")
    env = DockerEnvironment(language=language)
    docker_environments[language] = env
    return env

async def run_code(language: str, code: str) -> Dict:
    """
    Execute code in a Docker container
    
    Args:
        language: Programming language (python, java, cpp, etc.)
        code: Source code to execute
        
    Returns:
        Dictionary with execution results
    """
    # Normalize language name
    language = language.lower().strip()
    
    # Map language aliases to standard names
    language = LANGUAGE_ALIASES.get(language, language)
    
    # Check if language is supported
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {language}, falling back to Python")
        language = "python"
    
    # Get Docker environment
    env = get_environment(language)
    
    # Connect to container
    if not env.active:
        connect_result = await env.connect()
        if not connect_result.get("success", False):
            return {"error": connect_result.get("error", "Failed to connect to container")}
    
    # Explicitly activate the language environment
    env._activate_language_environment()
    
    # Write code to a file with appropriate extension
    extension = SUPPORTED_LANGUAGES[env.language]["file_extension"]
    
    # Special handling for Java - use class name as filename
    if language.lower() == 'java':
        # For Java, we need to use the class name as the filename
        try:
            # Look for the main class name
            # This is a simple check for "public class X" without using regex
            lines = code.split('\n')
            class_name = None
            for line in lines:
                line = line.strip()
                if line.startswith('public class '):
                    parts = line.split('public class ', 1)[1].split('{')[0].strip()
                    class_name = parts.split()[0].strip()
                    break
            
            if class_name:
                filename = f"{class_name}{extension}"
                logger.info(f"Using Java class name as filename: {filename}")
            else:
                filename = f"program{extension}"
                logger.info(f"No Java class name found, using default filename: {filename}")
        except Exception as e:
            logger.error(f"Error extracting Java class name: {str(e)}")
            filename = f"program{extension}"
    else:
        filename = f"program{extension}"
    
    write_result = await env.write_file(filename, code)
    
    if not write_result.get("success", False):
        return {"error": write_result.get("error", "Failed to write code file")}
    
    # Execute the code
    return await env.execute_code(filename)

# Function to generate docker-compose config for language environments
def generate_docker_compose_config() -> str:
    """
    Generate docker-compose configuration for all language environments
    
    Returns:
        docker-compose.yml content for language environments
    """
    # Start with version and services
    config = """version: '3'

services:
"""
    
    # Add each language environment
    for language, info in SUPPORTED_LANGUAGES.items():
        if language == "python":
            image = "python:3.11-slim"
            setup_cmds = "pip install numpy pandas matplotlib"
        elif language == "java":
            image = "openjdk:17-slim"
            setup_cmds = "apt-get update && apt-get install -y --no-install-recommends ca-certificates-java"
        elif language == "cpp":
            image = "gcc:11-bullseye"
            setup_cmds = "apt-get update && apt-get install -y --no-install-recommends build-essential"
        elif language == "javascript":
            image = "node:18-slim"
            setup_cmds = "npm install -g axios"
        elif language == "typescript":
            image = "node:18-slim"
            setup_cmds = "npm install -g typescript axios"
        elif language == "ruby":
            image = "ruby:3.2-slim"
            setup_cmds = "gem install bundler"
        elif language == "go":
            image = "golang:1.20-bullseye"
            setup_cmds = "go get -u github.com/gorilla/mux"
        elif language == "rust":
            image = "rust:1.70-slim"
            setup_cmds = "rustup component add rustfmt"
        elif language == "php":
            image = "php:8.2-cli"
            setup_cmds = "apt-get update && apt-get install -y --no-install-recommends php-cli"
        else:
            continue  # Skip unknown languages
        
        # Generate configuration for this language
        container_name = info["container_name"]
        
        config += f"""  {language}_env:
    container_name: {container_name}
    image: {image}
    command: tail -f /dev/null
    volumes:
      - {language}_code:/app
    working_dir: /app
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
"""
        
        # Add init script
        setup_script = f"""echo "Setting up {language} environment..."
{setup_cmds}
echo "{language} environment ready!"
"""
        config += f"""    healthcheck:
      test: ["CMD", "echo", "healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    environment:
      - SETUP_SCRIPT={setup_script}

"""
    
    # Add volumes section
    config += "\nvolumes:\n"
    for language in SUPPORTED_LANGUAGES.keys():
        config += f"  {language}_code:\n"
    
    return config

# Save docker-compose configuration to a file
def save_docker_compose_config(output_path: str = "docker-compose.lang-env.yml") -> bool:
    """
    Save docker-compose configuration for language environments to a file
    
    Args:
        output_path: Path to save the configuration
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config = generate_docker_compose_config()
        
        with open(output_path, "w") as f:
            f.write(config)
            
        logger.info(f"Docker Compose configuration saved to {output_path}")
        logger.info(f"Run 'docker-compose -f {output_path} up -d' to start all language environments")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save Docker Compose configuration: {str(e)}")
        return False 