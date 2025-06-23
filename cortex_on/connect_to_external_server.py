import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime

import nest_asyncio
from colorama import Fore, Style, init
import logfire
from mcp import ClientSession, StdioServerParameters
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

init(autoreset=True)  # Initialize colorama with autoreset=True

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio

load_dotenv()  

class StdioServerProvider:
    """Class for creating and managing MCPServerStdio instances from a JSON configuration file"""
    
    def __init__(self, config_path: str = 'config/external_mcp_servers.json'):
        self.config_path = config_path
        self.servers: Dict[str, MCPServerStdio] = {}
        self.server_configs: Dict[str, Dict[str, Any]] = {}
        self.server_tools: Dict[str, List[Dict[str, Any]]] = {}
        self.server_status: Dict[str, Dict[str, Any]] = {}
        self.registered_tool_names: List[str] = []  # Track all registered tool names to ensure uniqueness
        self.active_servers: List[MCPServerStdio] = []  # Track currently active servers
        
    async def shutdown_servers(self):
        """Properly shut down all active servers"""
        for server in self.active_servers:
            try:
                if hasattr(server, 'close') and callable(server.close):
                    await server.close()
                elif hasattr(server, '__aexit__') and callable(server.__aexit__):
                    await server.__aexit__(None, None, None)
                logfire.info(f"Shut down MCP server: {server}")
            except Exception as e:
                print(f"Error shutting down server: {str(e)}")
        
        # Clear the active servers list
        self.active_servers = []
        self.servers = {}
        self.server_tools = {}
        print("All servers have been shut down")

    async def load_servers(self) -> Tuple[List[MCPServerStdio], str]:
        """Load server configurations from JSON and create MCPServerStdio instances"""
        # First shut down any existing servers
        await self.shutdown_servers()
        
        # Clear registered tool names before loading new servers
        self.registered_tool_names = []
        
        # Check if config file exists in the specified path or try to find it
        if not os.path.exists(self.config_path):
            # Try to find it relative to the current file
            alt_path = os.path.join(os.path.dirname(__file__), self.config_path)
            if os.path.exists(alt_path):
                self.config_path = alt_path
            else:
                # Try to find it in the parent directory
                parent_dir = os.path.dirname(os.path.dirname(__file__))
                alt_path = os.path.join(parent_dir, self.config_path)
                if os.path.exists(alt_path):
                    self.config_path = alt_path
                else:
                    raise FileNotFoundError(f"Could not find config file: {self.config_path}")
        
        print(f"Loading stdio server configuration from: {self.config_path}")
        
        # Load the configuration file
        with open(self.config_path, 'r') as f:
            self.server_configs = json.load(f)
        
        # Create MCPServerStdio instances for each server
        stdio_servers = []
        server_names = []
        
        for server_name, config in self.server_configs.items():
            # Skip servers without a command
            if 'command' not in config or not config['command']:
                print(f"Skipping {server_name} - no command specified")
                continue
            
            if config['status'] == "disabled":
                print(f"Skipping {server_name} - server is disabled")
                continue
            
            command = config['command']
            args = config.get('args', [])
            env = config.get('env', {})
            
            # Create the MCPServerStdio instance
            try:
                # Use namespaced tool names by setting the namespace parameter
                server = MCPServerStdio(
                    command,
                    args=args,
                    env=env
                )
                
                self.servers[server_name] = server
                stdio_servers.append(server)
                server_names.append(server_name)
                self.active_servers.append(server)  # Track in active servers list
                
                # Initialize server status
                self.server_status[server_name] = {
                    "status": "initializing",
                    "last_update": datetime.now().isoformat()
                }
                
                print(f"Created MCPServerStdio for {server_name} with command: {command} {' '.join(args)}")
            except Exception as e:
                print(f"Error creating MCPServerStdio for {server_name}: {str(e)}")
        
        # Wait for servers to initialize before attempting to discover tools
        await asyncio.sleep(2)
        
        # Try to discover tools from all servers
        for server_name in server_names:
            print(f"Attempting to discover tools for {server_name}...")
            await self.get_server_tools(server_name)
        
        # Generate a combined system prompt with server information
        system_prompt = self._generate_system_prompt(server_names)
        
        return stdio_servers, system_prompt
    
    def _generate_system_prompt(self, server_names: List[str]) -> str:
        """Generate a system prompt for the agent with information about available servers and their tools"""
        if not server_names:
            return "You are an AI assistant that can help with various tasks."
        
        servers_list = ", ".join([f"`{name}`" for name in server_names])
        
        prompt = f"""[EXTERNAL SERVER CAPABILITIES]
                """
        
        # Add details about each server and its tools if available
        for server_name in server_names:
            config = self.server_configs.get(server_name, {})
            description = config.get('description', f"MCP server for {server_name}")
            
            prompt += f"""- {server_name}:
                        Description: {description}
                        Usage scenarios:
                        """
            
            # Add general usage scenarios based on server description
            keywords = server_name.lower().split('-')
            if "github" in keywords:
                prompt += """    - Repository operations
                            - Code browsing and analysis
                            - Issue and PR management
                        """
            elif "google" in keywords and "maps" in keywords:
                prompt += """    - Geocoding and location services
                            - Directions and routing
                            - Place search and information
                        """
            else:
                # Generic description based on server name
                prompt += f"""    - {server_name.replace('-', ' ').title()} operations
                        """
            
            # Add tool information
            prompt += "  Available tools:\n"
            
            # Use any tools we've discovered
            tools = self.server_tools.get(server_name, [])
            if tools:
                for tool in tools:
                    tool_name = tool.get("name", f"{server_name}.unknown_tool")
                    tool_description = tool.get("description", "No description available")
                    prompt += f"    - {tool_name}: {tool_description}\n"
            else:
                # If no tools are discovered, provide generic information
                prompt += f"    - Various tools prefixed with '{server_name}.'\n"
            
        prompt += """
                [HOW TO USE EXTERNAL SERVERS]
                1. When a user's task requires capabilities from an external server:
                - Identify which server is most appropriate based on the task description
                - Use the server's tools directly with the server name prefix (e.g., {server}.tool_name)
                - Include all required parameters for the tool

                2. Server selection guidelines:
                """

        # Dynamically generate server selection guidelines based on available servers
        for server_name in server_names:
            server_title = server_name.replace('-', ' ').title()
            prompt += f"   - For {server_title} operations: Choose the {server_name} server\n"

        prompt += """
                3. Important notes:
                - Always include the server name prefix with the tool name
                - Multiple servers can be used in the same task when needed
                - Provide detailed parameters based on the specific tool requirements
                        """
        
        return prompt

    async def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Fetch tool information from a running server by introspecting its capabilities"""
        if server_name not in self.servers:
            return []
            
        try:
            server = self.servers[server_name]
            tools = []
            
            # Access the private _mcp_api property to get tool information
            # Note: This is implementation-specific and might need adjustment
            # based on the actual MCPServerStdio implementation
            if hasattr(server, '_mcp_api') and server._mcp_api:
                api = server._mcp_api
                
                # Check if the API has a tool manager
                if hasattr(api, '_tool_manager'):
                    tool_manager = api._tool_manager
                    
                    # Get tools from the tool manager
                    if hasattr(tool_manager, '_tools') and tool_manager._tools:
                        for tool_name, tool_info in tool_manager._tools.items():
                            # Ensure tool name has server namespace prefix
                            if not tool_name.startswith(f"{server_name}."):
                                prefixed_name = f"{server_name}.{tool_name}"
                            else:
                                prefixed_name = tool_name
                            
                            # Check if this tool name is already registered
                            if prefixed_name in self.registered_tool_names:
                                # Make the name unique by adding a suffix
                                base_name = prefixed_name
                                suffix = 1
                                while f"{base_name}_{suffix}" in self.registered_tool_names:
                                    suffix += 1
                                prefixed_name = f"{base_name}_{suffix}"
                                
                            # Add to the registered names list
                            self.registered_tool_names.append(prefixed_name)
                                
                            # Extract description if available
                            description = "No description available"
                            if hasattr(tool_info, 'description') and tool_info.description:
                                description = tool_info.description
                            elif hasattr(tool_info, '__doc__') and tool_info.__doc__:
                                description = tool_info.__doc__.strip()
                                
                            tools.append({
                                "name": prefixed_name,
                                "description": description
                            })
            
            # If we couldn't get tools through introspection, try to get schema
            if not tools and hasattr(server, 'get_schema'):
                try:
                    # Some MCP servers might have a get_schema method
                    schema = await server.get_schema()
                    if schema and 'tools' in schema:
                        for tool in schema['tools']:
                            name = tool.get('name', '')
                            # Ensure tool name has server namespace prefix
                            if not name.startswith(f"{server_name}."):
                                prefixed_name = f"{server_name}.{name}"
                            else:
                                prefixed_name = name
                                
                            # Check if this tool name is already registered
                            if prefixed_name in self.registered_tool_names:
                                # Make the name unique by adding a suffix
                                base_name = prefixed_name
                                suffix = 1
                                while f"{base_name}_{suffix}" in self.registered_tool_names:
                                    suffix += 1
                                prefixed_name = f"{base_name}_{suffix}"
                                
                            # Add to the registered names list
                            self.registered_tool_names.append(prefixed_name)
                                
                            tools.append({
                                "name": prefixed_name,
                                "description": tool.get('description', f"Tool from {server_name}")
                            })
                except Exception as schema_err:
                    print(f"Error getting schema from {server_name}: {str(schema_err)}")
            
            # Fallback for when we can't directly access the tool information:
            # We'll use some typical tools based on server name to provide useful information
            if not tools:
                fallback_tools = []
                
                if server_name == "github":
                    fallback_tools = [
                        {"base_name": "search_repositories", "description": "Search for GitHub repositories"},
                        {"base_name": "get_repository", "description": "Get details about a specific repository"},
                        {"base_name": "list_issues", "description": "List issues for a repository"},
                        {"base_name": "create_issue", "description": "Create a new issue in a repository"},
                        {"base_name": "search_code", "description": "Search for code within repositories"}
                    ]
                elif server_name == "google-maps":
                    fallback_tools = [
                        {"base_name": "geocode", "description": "Convert addresses to geographic coordinates"},
                        {"base_name": "directions", "description": "Get directions between locations"},
                        {"base_name": "places", "description": "Search for places near a location"},
                        {"base_name": "distance_matrix", "description": "Calculate distance and travel time"}
                    ]
                else:
                    fallback_tools = [
                        {"base_name": "use", "description": f"Use the {server_name} service"}
                    ]
                    
                # Process the fallback tools with unique naming
                for tool_info in fallback_tools:
                    base_name = tool_info["base_name"]
                    prefixed_name = f"{server_name}.{base_name}"
                    
                    # Check if this tool name is already registered
                    if prefixed_name in self.registered_tool_names:
                        # Make the name unique by adding a suffix
                        suffix = 1
                        while f"{prefixed_name}_{suffix}" in self.registered_tool_names:
                            suffix += 1
                        prefixed_name = f"{prefixed_name}_{suffix}"
                    
                    # Add to the registered names list
                    self.registered_tool_names.append(prefixed_name)
                    
                    tools.append({
                        "name": prefixed_name,
                        "description": tool_info["description"]
                    })
                    
                print(f"Using fallback tool definitions for {server_name} - actual tools couldn't be discovered")
                
            # Store and return the tools
            self.server_tools[server_name] = tools
            print(f"Discovered {len(tools)} tools for {server_name}")
            return tools
        except Exception as e:
            print(f"Error discovering tools from {server_name}: {str(e)}")
            return []

    async def monitor_server_status(self, server_name: str, callback: callable) -> None:
        """
        Set up monitoring for a server's status and call the callback with updates
        
        Args:
            server_name: The name of the server to monitor
            callback: An async function to call with status updates (takes server_name and status dict)
        """
        if server_name not in self.servers:
            return
            
        try:
            # Set initial status
            status = {
                "status": "monitoring",
                "progress": 75,
                "last_update": datetime.now().isoformat()
            }
            
            # Call the callback with initial status
            try:
                await callback(server_name, status)
            except Exception as cb_err:
                logfire.error(f"Error calling status callback: {str(cb_err)}")
                
            # Check server health periodically
            check_count = 0
            while server_name in self.servers:
                check_count += 1
                
                # Get the server
                server = self.servers[server_name]
                is_healthy = False
                
                # Try to determine if the server is healthy
                try:
                    if hasattr(server, '_mcp_api') and server._mcp_api:
                        # We'll consider it healthy if it has an API
                        is_healthy = True
                        
                        # Get more detailed health info if available
                        if hasattr(server._mcp_api, 'health') and callable(server._mcp_api.health):
                            health_info = await server._mcp_api.health()
                            if isinstance(health_info, dict):
                                status.update(health_info)
                except Exception:
                    is_healthy = False
                
                # Update the status based on health check
                if is_healthy:
                    status = {
                        "status": "running",
                        "progress": 100,
                        "health": "ok",
                        "last_update": datetime.now().isoformat(),
                        "check_count": check_count
                    }
                else:
                    status = {
                        "status": "degraded",
                        "progress": 80,
                        "health": "degraded",
                        "last_update": datetime.now().isoformat(),
                        "check_count": check_count
                    }
                
                # Call the callback with the status
                try:
                    await callback(server_name, status)
                except Exception as cb_err:
                    logfire.error(f"Error calling status callback: {str(cb_err)}")
                
                # Wait before the next check
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            logfire.error(f"Error monitoring server {server_name}: {str(e)}")
            
            # Try to send a final error status
            try:
                status = {
                    "status": "error",
                    "progress": 0,
                    "error": str(e),
                    "last_update": datetime.now().isoformat()
                }
                await callback(server_name, status)
            except Exception:
                pass

server_provider = StdioServerProvider()