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

const GoogleMapsViewContent = () => {
   const [apiKey, setApiKey] = useState("");
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
                  server_name: "google-maps",
                  server_secret: apiKey,
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
      if (message.toLowerCase().includes("invalid key")) {
         return "The Google Maps API key you entered is invalid. Please check your key and try again.";
      }
      if (message.toLowerCase().includes("quota exceeded")) {
         return "You have exceeded your Google Maps API quota. Please check your usage limits.";
      }
      return "There was an error processing your request. Please try again.";
   };

   return (
      <div className="p-8 space-y-8">
         <div className="space-y-4">
            <h1 className="text-4xl font-bold">Google Maps MCP</h1>
            <p className="text-gray-400">
               Configure your Google Maps API key to enable Google Maps
               integration. Create a key with Maps JavaScript API enabled.
            </p>
         </div>

         <div className="space-y-4 max-w-xl">
            <Input
               type="password"
               placeholder="Enter your Google Maps API Key"
               className="bg-gray-800/50 border-gray-700"
               value={apiKey}
               onChange={(e) => setApiKey(e.target.value)}
            />
            <div className="flex gap-4">
               <Button
                  className="px-8"
                  onClick={() => handleToggle("enable")}
                  disabled={isLoading || !apiKey}
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

const GoogleMapsView = () => {
   return (
      <ErrorBoundary>
         <GoogleMapsViewContent />
      </ErrorBoundary>
   );
};

export default GoogleMapsView;
