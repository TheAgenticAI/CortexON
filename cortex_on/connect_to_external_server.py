import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple, Union

import nest_asyncio
from colorama import Fore, Style, init
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
        
    async def load_servers(self) -> Tuple[List[MCPServerStdio], str]:
        """Load server configurations from JSON and create MCPServerStdio instances"""
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
            
            command = config['command']
            args = config.get('args', [])
            env = config.get('env', {})
            
            # Create the MCPServerStdio instance
            try:
                server = MCPServerStdio(
                    command,
                    args=args,
                    env=env
                )
                
                self.servers[server_name] = server
                stdio_servers.append(server)
                server_names.append(server_name)
                
                print(f"Created MCPServerStdio for {server_name} with command: {command} {' '.join(args)}")
            except Exception as e:
                print(f"Error creating MCPServerStdio for {server_name}: {str(e)}")
        
        # Generate a combined system prompt with server information
        system_prompt = self._generate_system_prompt(server_names)
        
        return stdio_servers, system_prompt
    
    def _generate_system_prompt(self, server_names: List[str]) -> str:
        """Generate a system prompt for the agent with information about available servers"""
        if not server_names:
            return "You are an AI assistant that can help with various tasks."
        
        servers_list = ", ".join([f"`{name}`" for name in server_names])
        
        prompt = f"""You also have access to the following MCP servers: {servers_list}.
                Each server provides specialized tools that you can use to complete tasks:

                """
        
        # Add details about each server and its tools if available
        for server_name in server_names:
            config = self.server_configs.get(server_name, {})
            description = config.get('description', f"MCP server for {server_name}")
            
            prompt += f"- {server_name}: {description}\n"
        
        prompt += """
            When using these servers, reference them by their tools as available.
            """
        
        return prompt

server_provider = StdioServerProvider()