import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { mcpService, MCPServerConfig } from "@/services/mcpService";

const GithubView = () => {
   const [token, setToken] = useState("");
   const [serverStatus, setServerStatus] = useState<MCPServerConfig | null>(
      null
   );
   const [isLoading, setIsLoading] = useState(false);
   const [feedbackMessage, setFeedbackMessage] = useState("");
   const [feedbackType, setFeedbackType] = useState<"success" | "error" | "">(
      ""
   );

   useEffect(() => {
      fetchServerStatus();
   }, []);

   const fetchServerStatus = async (isUserAction = false) => {
      try {
         const status = await mcpService.getServerDetails("github");
         setServerStatus(status);
      } catch (error) {
         setServerStatus(null);
         if (isUserAction) {
            setFeedbackMessage("Failed to fetch server status.");
            setFeedbackType("error");
         }
      }
   };

   const handleSubmit = async () => {
      if (!token) {
         setFeedbackMessage("Please enter a token");
         setFeedbackType("error");
         return;
      }

      setIsLoading(true);
      setFeedbackMessage("");
      setFeedbackType("");
      try {
         const response = await mcpService.toggleServer("github", token);
         if (response.status === "success") {
            setFeedbackMessage(response.message);
            setFeedbackType("success");
            await fetchServerStatus(true);
         } else {
            setFeedbackMessage(response.message);
            setFeedbackType("error");
         }
      } catch (error) {
         setFeedbackMessage("Failed to enable GitHub MCP server");
         setFeedbackType("error");
      } finally {
         setIsLoading(false);
      }
   };

   const handleDisable = async () => {
      setIsLoading(true);
      setFeedbackMessage("");
      setFeedbackType("");
      try {
         const response = await mcpService.toggleServer(
            "github",
            token,
            "disable"
         );
         if (response.status === "success") {
            setFeedbackMessage(response.message);
            setFeedbackType("success");
            await fetchServerStatus(true);
         } else {
            setFeedbackMessage(response.message);
            setFeedbackType("error");
         }
      } catch (error) {
         setFeedbackMessage("Failed to disable GitHub MCP server");
         setFeedbackType("error");
      } finally {
         setIsLoading(false);
      }
   };

   return (
      <div className="p-8 space-y-8">
         <div className="space-y-4">
            <h1 className="text-4xl font-bold text-center">GitHub MCP</h1>
            <p className="text-gray-400 text-center">
               Configure GitHub integration for MCP. Enter your Personal Access
               Token to enable the service.
            </p>
            {serverStatus && (
               <div
                  className={`p-4 rounded-lg text-center ${
                     serverStatus.status === "enabled"
                        ? "bg-green-500/20"
                        : "bg-gray-500/20"
                  }`}
               >
                  <p className="font-medium">
                     Status:{" "}
                     <span
                        className={
                           serverStatus.status === "enabled"
                              ? "text-green-400"
                              : "text-gray-400"
                        }
                     >
                        {serverStatus.status}
                     </span>
                  </p>
               </div>
            )}
         </div>

         <div className="space-y-4 max-w-xl mx-auto">
            <Input
               type="password"
               placeholder="Enter your Personal Access Token"
               className="bg-gray-800/50 border-gray-700"
               value={token}
               onChange={(e) => setToken(e.target.value)}
               disabled={isLoading}
            />
            <div className="flex gap-4 justify-center">
               <Button
                  className="px-8"
                  onClick={handleSubmit}
                  disabled={isLoading || serverStatus?.status === "enabled"}
               >
                  {isLoading ? "Enabling..." : "Enable"}
               </Button>
               {serverStatus?.status === "enabled" && (
                  <Button
                     variant="destructive"
                     className="px-8"
                     onClick={handleDisable}
                     disabled={isLoading}
                  >
                     {isLoading ? "Disabling..." : "Disable"}
                  </Button>
               )}
            </div>
            {feedbackMessage && (
               <div
                  className={`mt-2 text-center text-sm ${
                     feedbackType === "success"
                        ? "text-green-400"
                        : "text-red-400"
                  }`}
               >
                  {feedbackMessage}
               </div>
            )}
         </div>
      </div>
   );
};

export default GithubView;
