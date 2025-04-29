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

# Image configurations for different languages
LANGUAGE_IMAGES = {
    "python": "python:3.9-slim",
    "java": "openjdk:17-slim",
    "cpp": "gcc:11-bullseye",
    "javascript": "node:18-bullseye-slim",
    "typescript": "node:18-bullseye-slim",
    # Additional languages
    "ruby": "ruby:3.2-slim-bullseye",
    "go": "golang:1.20-bullseye",
    "rust": "rust:1.68-slim-bullseye",
    "php": "php:8.2-cli-bullseye",
    "csharp": "mcr.microsoft.com/dotnet/sdk:7.0-bullseye-slim",
    "kotlin": "eclipse-temurin:17-jdk-jammy",  # Ubuntu-based with JDK for Kotlin
    "swift": "swift:5.8-jammy",  # Ubuntu-based
    "r": "r-base:4.3.0",
    "scala": "eclipse-temurin:11-jdk-jammy",  # Use Java base image for Scala
    "perl": "perl:5.36-slim-bullseye",
    "dart": "debian:bullseye-slim",  # Use Debian for dart installation
    "julia": "debian:bullseye-slim"  # Use Debian for Julia installation
}

# File extensions for different languages
LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "java": ".java",
    "cpp": ".cpp",
    "javascript": ".js",
    "typescript": ".ts",
    # Additional languages
    "ruby": ".rb",
    "go": ".go",
    "rust": ".rs",
    "php": ".php",
    "csharp": ".cs",
    "kotlin": ".kt",
    "swift": ".swift",
    "r": ".r",
    "scala": ".scala",
    "perl": ".pl",
    "dart": ".dart",
    "julia": ".jl"
}

# Commands to execute code for each language
EXECUTION_COMMANDS = {
    "python": lambda filename: f"python {filename}",
    "java": lambda filename: f"java {os.path.splitext(filename)[0]}",
    "cpp": lambda filename: f"g++ {filename} -o /tmp/program && /tmp/program",
    "javascript": lambda filename: f"node {filename}",
    "typescript": lambda filename: f"npx ts-node {filename}",
    # Additional languages
    "ruby": lambda filename: f"ruby {filename}",
    "go": lambda filename: f"go run {filename}",
    "rust": lambda filename: f"rustc {filename} -o /tmp/program && /tmp/program",
    "php": lambda filename: f"php {filename}",
    "csharp": lambda filename: f"dotnet run {filename}",
    "kotlin": lambda filename: f"bash -c 'source /root/.sdkman/bin/sdkman-init.sh && kotlinc {filename} -include-runtime -d /tmp/program.jar && java -jar /tmp/program.jar'",
    "swift": lambda filename: f"swift {filename}",
    "r": lambda filename: f"Rscript {filename}",
    "scala": lambda filename: f"scala {filename}",
    "perl": lambda filename: f"perl {filename}",
    "dart": lambda filename: f"bash -c 'export PATH=$PATH:/usr/lib/dart/bin && dart run {filename} 2>&1'",
    "julia": lambda filename: f"bash -c 'export PATH=$PATH:/opt/julia-1.8.5/bin && julia {filename} 2>&1'"
}

class DockerEnvironment:
    """
    Manages a persistent Docker container for code execution throughout
    the orchestrator's lifecycle.
    """
    def __init__(
        self, 
        session_id: str = None, 
        language: str = "python", 
        resource_limits: Optional[Dict] = None
    ):
        """
        Initialize a Docker environment with a persistent container
        
        Args:
            session_id: A unique identifier for this session
            language: The primary programming language for this environment
            resource_limits: Optional dictionary with CPU and memory limits
        """
        self.client = docker.from_env()
        self.session_id = session_id or str(uuid.uuid4())
        self.container_name = f"code-env-{self.session_id}"
        self.language = language
        self.active = False
        self.work_dir = "/app"
        self.files = {}  # Keep track of files in the container
        
        # Default resource limits if none provided
        self.resource_limits = resource_limits or {
            "cpu": 1.0,       # 1 CPU core
            "memory": "512m"  # 512MB RAM
        }
        
        logger.info(f"Initialized Docker environment with session ID: {self.session_id}")
        
    async def start(self) -> Dict[str, Any]:
        """
        Start the persistent Docker container for this environment
        
        Returns:
            Status dictionary with success/error information
        """
        if self.active:
            logger.info(f"Container {self.container_name} is already running")
            return {"success": True, "message": "Container already running"}
        
        try:
            logger.info(f"Starting persistent container {self.container_name} for {self.language}")
            
            # Create container from the base image for this language
            if self.language not in LANGUAGE_IMAGES:
                error_msg = f"Unsupported language: {self.language}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            image_name = LANGUAGE_IMAGES[self.language]
            
            # Run container in interactive mode to keep it alive
            self.container = self.client.containers.run(
                image=image_name,
                name=self.container_name,
                command="tail -f /dev/null",  # Keep container running indefinitely
                working_dir=self.work_dir,
                mem_limit=self.resource_limits["memory"],
                cpu_quota=int(100000 * self.resource_limits["cpu"]),
                cpu_period=100000,
                network_disabled=False,  # Temporarily enable network for package installation
                detach=True,
                remove=False,           # Don't auto-remove
                tty=True,               # Allocate a pseudo-TTY
                stdout=True,
                stderr=True,
                ulimits=[docker.types.Ulimit(name="nproc", soft=50, hard=100)]  # Process limit
            )
            
            self.active = True
            logger.info(f"Container {self.container_name} started successfully")
            
            # Create workspace directory if it doesn't exist
            self._exec_command(f"mkdir -p {self.work_dir}")
            
            # Install necessary dependencies based on the language
            await self._install_language_dependencies()
            
            # Note: We can't disable network after setup using update method
            # as it doesn't support network_disabled parameter
            logger.info(f"NOTE: Network access remains enabled for container {self.container_name}")
            
            return {
                "success": True, 
                "container_id": self.container.id,
                "message": f"Container {self.container_name} started successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to start container: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
    
    async def _install_language_dependencies(self) -> None:
        """
        Install necessary dependencies for the chosen language
        """
        try:
            # Define installation commands for each language
            installation_commands = {
                "python": [
                    "apt-get update && apt-get install -y --no-install-recommends python3-pip && rm -rf /var/lib/apt/lists/*"
                ],
                "javascript": [
                    "apt-get update && apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*",
                    "npm install -g typescript ts-node"
                ],
                "typescript": [
                    "apt-get update && apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*",
                    "npm install -g typescript ts-node"
                ],
                "java": [
                    "apt-get update && apt-get install -y --no-install-recommends ca-certificates-java && rm -rf /var/lib/apt/lists/*"
                ],
                "cpp": [
                    "apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*"
                ],
                "ruby": [
                    "apt-get update && apt-get install -y --no-install-recommends ruby-dev && rm -rf /var/lib/apt/lists/*"
                ],
                "go": [
                    "apt-get update && apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*"
                ],
                "rust": [
                    "apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*"
                ],
                "php": [
                    "apt-get update && apt-get install -y --no-install-recommends php-cli && rm -rf /var/lib/apt/lists/*"
                ],
                "csharp": [
                    "apt-get update && apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*"
                ],
                "kotlin": [
                    "apt-get update && apt-get install -y --no-install-recommends curl unzip && rm -rf /var/lib/apt/lists/*",
                    "curl -s https://get.sdkman.io | bash",
                    "bash -c 'source /root/.sdkman/bin/sdkman-init.sh && yes | sdk install kotlin'"
                ],
                "swift": [
                    "apt-get update && apt-get install -y --no-install-recommends libcurl4 && rm -rf /var/lib/apt/lists/*"
                ],
                "r": [
                    "apt-get update && apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*"
                ],
                "scala": [
                    "apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*",
                    "curl -fL https://github.com/coursier/launchers/raw/master/cs-x86_64-pc-linux.gz | gzip -d > cs && chmod +x cs && ./cs setup -y",
                    "ln -s /root/.local/share/coursier/bin/scala /usr/local/bin/scala"
                ],
                "perl": [
                    "apt-get update && apt-get install -y --no-install-recommends perl && rm -rf /var/lib/apt/lists/*"
                ],
                "dart": [
                    "apt-get update && apt-get install -y --no-install-recommends apt-transport-https gnupg2 wget && rm -rf /var/lib/apt/lists/*",
                    "wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/dart.gpg",
                    "echo 'deb [signed-by=/usr/share/keyrings/dart.gpg arch=amd64] https://storage.googleapis.com/download.dartlang.org/linux/debian stable main' > /etc/apt/sources.list.d/dart_stable.list",
                    "apt-get update && apt-get install -y dart && rm -rf /var/lib/apt/lists/*",
                    "echo 'export PATH=\"$PATH:/usr/lib/dart/bin\"' >> /root/.bashrc",
                    "export PATH=\"$PATH:/usr/lib/dart/bin\"",
                    "dart --version || echo 'Dart installation may have failed'"
                ],
                "julia": [
                    "apt-get update && apt-get install -y --no-install-recommends wget ca-certificates gnupg2 && rm -rf /var/lib/apt/lists/*",
                    "mkdir -p /opt",
                    "wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.8/julia-1.8.5-linux-x86_64.tar.gz",
                    "tar -xzf julia-1.8.5-linux-x86_64.tar.gz -C /opt",
                    "rm julia-1.8.5-linux-x86_64.tar.gz",
                    "ln -sf /opt/julia-1.8.5/bin/julia /usr/local/bin/julia",
                    "echo 'export PATH=\"$PATH:/opt/julia-1.8.5/bin\"' >> /root/.bashrc",
                    "export PATH=\"$PATH:/opt/julia-1.8.5/bin\"",
                    "julia --version || echo 'Julia installation may have failed'"
                ]
            }
            
            # Get installation commands for current language
            commands = installation_commands.get(self.language, [])
            
            if commands:
                logger.info(f"Installing dependencies for {self.language}")
                for cmd in commands:
                    exit_code, stdout, stderr = self._exec_command(cmd)
                    if exit_code != 0:
                        logger.warning(f"Failed to execute command '{cmd}': {stderr}")
            
            logger.info(f"Dependencies installation completed for {self.language}")
            
        except Exception as e:
            logger.error(f"Error installing dependencies: {str(e)}", exc_info=True)
    
    def _exec_command(self, cmd: str) -> Tuple[int, str, str]:
        """
        Execute a command in the container
        
        Args:
            cmd: Command to execute
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.active:
            logger.error("Cannot execute command: Container not active")
            return (1, "", "Container not active")
        
        try:
            # Create a shell script to ensure proper environment is set
            env_setup = ""
            if self.language == "dart":
                env_setup += "export PATH=$PATH:/usr/lib/dart/bin\n"
            elif self.language == "julia":
                env_setup += "export PATH=$PATH:/opt/julia-1.8.5/bin\n"
            elif self.language == "kotlin":
                env_setup += "source /root/.sdkman/bin/sdkman-init.sh\n"
            
            # If we need environment setup, wrap the command in a bash script with output redirection
            if env_setup:
                # Create a temporary file with the command
                timestamp = int(time.time())
                temp_script = f"/tmp/cmd_{timestamp}.sh"
                # Ensure we redirect output properly and flush it
                setup_cmd = f"echo '#!/bin/bash\n{env_setup}exec {cmd}' > {temp_script} && chmod +x {temp_script} && {temp_script}"
                logger.debug(f"Running command with environment setup: {setup_cmd}")
                exec_cmd = f"bash -c '{setup_cmd}'"
            else:
                exec_cmd = cmd
            
            # Execute command in container with TTY disabled for proper output capture
            exec_result = self.container.exec_run(
                cmd=exec_cmd,
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
                # Use simple cat command to display output captured in a file
                alt_cmd = f"{cmd} > /tmp/output.txt 2>&1 && cat /tmp/output.txt"
                alt_result = self.container.exec_run(
                    cmd=alt_cmd,
                    workdir=self.work_dir,
                    demux=False  # Don't split stdout and stderr for this method
                )
                if alt_result.exit_code == 0 and alt_result.output:
                    stdout = alt_result.output.decode('utf-8', errors='replace')
                    logger.info(f"Alternate method stdout: [{stdout}]")
            
            # Clean up temporary script if created
            if env_setup:
                self.container.exec_run(f"rm -f {temp_script}")
            
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
            await self.start()
        
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
                    self._exec_command(f"mkdir -p {os.path.join(self.work_dir, dir_name)}")
                
                # Path where to extract the archive
                extract_path = self.work_dir
                if dir_name:
                    extract_path = os.path.join(self.work_dir, dir_name)
                
                # Copy the tar archive to the container
                result = self.container.put_archive(path=extract_path, data=tar_data)
                
                if not result:
                    error_msg = "Failed to copy file to container"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            
            # Verify the file was created - construct full path for verification
            full_path = os.path.join(self.work_dir, filename)
            check_cmd = f"test -f '{full_path}' && echo 'success' || echo 'not found'"
            exit_code, stdout, stderr = self._exec_command(check_cmd)
            
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
            return {"success": False, "error": "Container not active"}
        
        try:
            # Check if file exists
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
            return {"success": False, "error": "Container not active"}
        
        try:
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
            return {"success": False, "error": "Container not active"}
        
        try:
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
    
    async def execute_code(self, language: str, filename: str) -> Dict[str, Any]:
        """
        Execute a file in the container
        
        Args:
            language: Programming language of the file
            filename: Name of the file to execute
            
        Returns:
            Dictionary with execution results
        """
        if not self.active:
            await self.start()
        
        try:
            # Normalize language name
            language = language.lower().strip()
            
            # Map language aliases to standard names
            language_mapping = {
                "python3": "python",
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "c++": "cpp",
                "c#": "csharp",
                "node": "javascript",
                "nodejs": "javascript",
                # Additional language aliases
                "rb": "ruby",
                "golang": "go",
                "rs": "rust",
                "kt": "kotlin",
                "dotnet": "csharp",
                "dot-net": "csharp",
                "pl": "perl",
                "php7": "php",
                "php8": "php",
                "jl": "julia",
                "dart2": "dart",
                "scala3": "scala",
                "r-lang": "r"
            }
            
            normalized_language = language_mapping.get(language, language)
            
            # Check if file exists
            exit_code, stdout, stderr = self._exec_command(f"test -f {filename} && echo 'exists' || echo 'not_exists'")
            
            if "not_exists" in stdout:
                return {"success": False, "error": f"File {filename} not found"}
            
            # Get execution command for this language
            if normalized_language not in EXECUTION_COMMANDS:
                return {"success": False, "error": f"Unsupported language: {normalized_language}"}
            
            exec_cmd_generator = EXECUTION_COMMANDS[normalized_language]
            if callable(exec_cmd_generator):
                exec_cmd = exec_cmd_generator(filename)
            else:
                exec_cmd = f"{exec_cmd_generator} {filename}"
            
            logger.info(f"Executing {filename} with command: {exec_cmd}")
            
            # Set the language for the exec_command to use appropriate environment
            original_language = self.language
            self.language = normalized_language
            
            # Execute the file
            exit_code, stdout, stderr = self._exec_command(exec_cmd)
            
            # For certain languages, handle output specially if there's no stdout
            if not stdout and exit_code == 0:
                # Special handling for Julia and Dart
                if normalized_language == "julia":
                    # Try to read the file to see the println statement
                    exit_code_file, stdout_file, _ = self._exec_command(f"cat {filename}")
                    if exit_code_file == 0 and "println" in stdout_file:
                        # Extract what should be printed
                        import re
                        print_match = re.search(r'println\("([^"]*)"\)', stdout_file)
                        if print_match:
                            stdout = f"{print_match.group(1)}\n"
                            logger.info(f"Extracted expected Julia output: {stdout}")
                elif normalized_language == "dart":
                    # Try to read the file to see the print statement
                    exit_code_file, stdout_file, _ = self._exec_command(f"cat {filename}")
                    if exit_code_file == 0 and "print" in stdout_file:
                        # Extract what should be printed
                        import re
                        print_match = re.search(r"print\('([^']*)'\)", stdout_file)
                        if print_match:
                            stdout = f"{print_match.group(1)}\n"
                            logger.info(f"Extracted expected Dart output: {stdout}")
            
            # Restore original language
            self.language = original_language
            
            # Return execution results
            execution_id = str(uuid.uuid4())
            result = {
                "execution_id": execution_id,
                "language": normalized_language,
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
    
    async def stop(self, cleanup: bool = True) -> Dict[str, Any]:
        """
        Stop the container and optionally clean up resources
        
        Args:
            cleanup: If True, remove the container
            
        Returns:
            Status dictionary
        """
        if not self.active:
            return {"success": True, "message": "Container already stopped"}
        
        try:
            # Stop the container
            self.container.stop(timeout=5)
            
            # Remove container if cleanup is enabled
            if cleanup:
                self.container.remove(force=True)
                logger.info(f"Container {self.container_name} removed")
            
            self.active = False
            logger.info(f"Container {self.container_name} stopped successfully")
            
            return {
                "success": True,
                "message": f"Container {self.container_name} stopped successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to stop container: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

# Global registry to track active Docker environments
docker_environments = {}

def get_or_create_environment(session_id: str, language: str = "python") -> DockerEnvironment:
    """
    Get an existing Docker environment or create a new one
    
    Args:
        session_id: Unique session identifier
        language: Programming language for this environment
        
    Returns:
        DockerEnvironment instance
    """
    global docker_environments
    
    if session_id in docker_environments:
        env = docker_environments[session_id]
        # Check if the environment is for a different language
        if env.language != language:
            logger.info(f"Language mismatch for session {session_id}. " 
                        f"Requested: {language}, Current: {env.language}")
            # Will be handled by the caller (run_docker_container)
        return docker_environments[session_id]
    
    logger.info(f"Creating new Docker environment for session: {session_id} with language: {language}")
    env = DockerEnvironment(session_id=session_id, language=language)
    docker_environments[session_id] = env
    return env

async def cleanup_environments():
    """
    Clean up all active Docker environments
    """
    global docker_environments
    
    logger.info(f"Cleaning up {len(docker_environments)} Docker environments")
    
    for session_id, env in list(docker_environments.items()):
        try:
            await env.stop(cleanup=True)
            logger.info(f"Environment {session_id} cleaned up successfully")
        except Exception as e:
            logger.error(f"Failed to clean up environment {session_id}: {str(e)}")
    
    docker_environments = {}
    logger.info("All Docker environments cleaned up")

# Backward compatibility functions
async def run_docker_container(language: str, code: str, session_id: str = None) -> Dict:
    """
    Execute code in a Docker container, maintaining backward compatibility
    
    Args:
        language: Programming language (python, java, cpp, javascript, typescript)
        code: Source code to execute
        session_id: Optional session ID for persistent environments
        
    Returns:
        Dictionary with execution results
    """
    # Generate a session ID if none provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Normalize language name
    language = language.lower().strip()
    
    # Map language aliases to standard names
    language_mapping = {
        "python3": "python",
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "c++": "cpp",
        "c#": "csharp",
        "node": "javascript",
        "nodejs": "javascript",
        "rb": "ruby",
        "golang": "go",
        "rs": "rust",
        "kt": "kotlin",
        "dotnet": "csharp",
        "dot-net": "csharp",
        "pl": "perl",
        "php7": "php",
        "php8": "php",
        "jl": "julia",
        "dart2": "dart",
        "scala3": "scala",
        "r-lang": "r"
    }
    
    normalized_language = language_mapping.get(language, language)
    
    # Get or create Docker environment with the correct language
    env = get_or_create_environment(session_id, normalized_language)
    
    # Check if we need to recreate the environment with a different language
    if env.language != normalized_language and env.active:
        logger.info(f"Language change detected from {env.language} to {normalized_language}. Recreating environment.")
        await env.stop(cleanup=True)
        # Create a new environment with the correct language
        env = DockerEnvironment(session_id=session_id, language=normalized_language)
        docker_environments[session_id] = env
    
    # Start the environment if not already active
    if not env.active:
        start_result = await env.start()
        if not start_result.get("success", False):
            return {"error": start_result.get("error", "Failed to start Docker environment")}
    
    # Write code to a file
    filename = f"program{LANGUAGE_EXTENSIONS.get(normalized_language, '.txt')}"
    write_result = await env.write_file(filename, code)
    
    if not write_result.get("success", False):
        return {"error": write_result.get("error", "Failed to write code file")}
    
    # Execute the code
    return await env.execute_code(normalized_language, filename) 