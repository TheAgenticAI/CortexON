import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import ErrorBoundary from "../ErrorBoundary";

interface ServerConfig {
   command?: string;
   args?: string[];
}

interface ServerResponse {
   status: "success" | "error";
   message: string;
   config?: ServerConfig;
}

const GithubViewContent = () => {
   const [token, setToken] = useState("");
   const [response, setResponse] = useState<ServerResponse | null>(null);
   const [isLoading, setIsLoading] = useState(false);

   const handleToggle = async (action: "enable" | "disable") => {
      setIsLoading(true);
      try {
         const response = await fetch(
            "http://localhost:8081/agent/mcp/servers",
            {
               method: "POST",
               headers: {
                  "Content-Type": "application/json",
               },
               body: JSON.stringify({
                  server_name: "github",
                  server_secret: token,
                  action,
               }),
            }
         );

         if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
         }

         const data = await response.json();
         setResponse(data);
      } catch (error) {
         setResponse({
            status: "error",
            message:
               error instanceof Error
                  ? error.message
                  : "Failed to connect to the server. Please try again.",
         });
      } finally {
         setIsLoading(false);
      }
   };

   const getErrorMessage = (message: string) => {
      if (message.toLowerCase().includes("invalid token")) {
         return "The GitHub token you entered is invalid. Please check your token and try again.";
      }
      if (message.toLowerCase().includes("unauthorized")) {
         return "The GitHub token you entered is not authorized. Please check your token permissions.";
      }
      if (message.toLowerCase().includes("expired")) {
         return "Your GitHub token has expired. Please generate a new token and try again.";
      }
      return "There was an error processing your request. Please try again.";
   };

   return (
      <div className="p-8 space-y-8">
         <div className="space-y-4">
            <h1 className="text-4xl font-bold">GitHub MCP</h1>
            <p className="text-gray-400">
               Configure your GitHub Personal Access Token to enable GitHub
               integration. Create a token with repo and workflow scopes.
            </p>
         </div>

         <div className="space-y-4 max-w-xl">
            <Input
               type="password"
               placeholder="Enter your Personal Access Token"
               className="bg-gray-800/50 border-gray-700"
               value={token}
               onChange={(e) => setToken(e.target.value)}
            />
            <div className="flex gap-4">
               <Button
                  className="px-8"
                  onClick={() => handleToggle("enable")}
                  disabled={isLoading || !token}
               >
                  {isLoading ? (
                     <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Enabling...
                     </>
                  ) : (
                     "Enable"
                  )}
               </Button>
               <Button
                  variant="destructive"
                  className="px-8"
                  onClick={() => handleToggle("disable")}
                  disabled={isLoading}
               >
                  {isLoading ? (
                     <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Disabling...
                     </>
                  ) : (
                     "Disable"
                  )}
               </Button>
            </div>
         </div>

         {response && (
            <div
               className={`p-4 rounded-lg ${
                  response.status === "success"
                     ? "bg-green-500/20 border border-green-500/50"
                     : "bg-red-500/20 border border-red-500/50"
               }`}
            >
               <p
                  className={
                     response.status === "success"
                        ? "text-green-400"
                        : "text-red-400"
                  }
               >
                  {response.status === "success"
                     ? response.message
                     : getErrorMessage(response.message)}
               </p>
               {response.status === "success" && response.config && (
                  <div className="mt-2 text-sm text-gray-400">
                     <p>Command: {response.config.command}</p>
                     {response.config.args && (
                        <p>Args: {response.config.args.join(" ")}</p>
                     )}
                  </div>
               )}
            </div>
         )}
      </div>
   );
};

const GithubView = () => {
   return (
      <ErrorBoundary>
         <GithubViewContent />
      </ErrorBoundary>
   );
};

export default GithubView;
