import axios from "axios";

const API_BASE_URL = "http://localhost:8081";

export interface MCPServer {
   name: string;
   description: string;
}

export interface MCPServerConfig {
   status: "enabled" | "disabled";
   config: {
      command?: string;
      args?: string[];
   };
}

export interface MCPServerResponse {
   status: "success" | "error";
   message: string;
   config?: MCPServerConfig["config"];
}

export const mcpService = {
   // Get all available MCP servers
   getServers: async (): Promise<MCPServer[]> => {
      const response = await axios.get(`${API_BASE_URL}/agent/mcp/servers`);
      return response.data;
   },

   // Get specific server details
   getServerDetails: async (serverName: string): Promise<MCPServerConfig> => {
      const response = await axios.get(
         `${API_BASE_URL}/agent/mcp/servers/${serverName}`
      );
      return response.data;
   },

   // Enable/Disable server
   toggleServer: async (
      serverName: string,
      serverSecret: string,
      action: "enable" | "disable" = "enable"
   ): Promise<MCPServerResponse> => {
      const response = await axios.post(`${API_BASE_URL}/agent/mcp/servers`, {
         server_name: serverName,
         server_secret: serverSecret,
         action,
      });
      return response.data;
   },
};
