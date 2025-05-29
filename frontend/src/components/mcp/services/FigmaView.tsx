import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Loader2 } from "lucide-react";

const FigmaViewContent = () => {
   const [token, setToken] = useState("");
   const [isLoading, setIsLoading] = useState(false);
   const [feedback, setFeedback] = useState<{
      status: "success" | "error";
      message: string;
   } | null>(null);

   const handleToggle = async (action: "enable" | "disable") => {
      if (!token.trim()) {
         setFeedback({ status: "error", message: "Please enter a token." });
         return;
      }
      setIsLoading(true);
      setFeedback(null);
      try {
         const response = await fetch(
            "http://localhost:8081/agent/mcp/servers",
            {
               method: "POST",
               headers: {
                  "Content-Type": "application/json",
               },
               body: JSON.stringify({
                  server_name: "figma",
                  server_secret: token,
                  action,
               }),
            }
         );
         if (response.ok) {
            setFeedback({
               status: "success",
               message:
                  action === "enable"
                     ? "Figma access token enabled successfully!"
                     : "Figma access token disabled successfully!",
            });
         } else {
            setFeedback({
               status: "error",
               message:
                  "Failed to update Figma access token. Please try again.",
            });
         }
      } catch {
         setFeedback({
            status: "error",
            message: "Network error. Please try again.",
         });
      } finally {
         setIsLoading(false);
      }
   };

   return (
      <div className="p-8 space-y-8">
         <div className="space-y-4">
            <h1 className="text-4xl font-bold">Figma MCP</h1>
            <p className="text-gray-400">
               Configure your Figma access token to enable Figma integration.
               Create a token with file:read scope.
            </p>
         </div>

         <div className="space-y-4 max-w-xl">
            <Input
               type="password"
               placeholder="Enter your Figma Access Token"
               className="bg-gray-800/50 border-gray-700"
               value={token}
               onChange={(e) => setToken(e.target.value)}
            />
            <div className="flex gap-4">
               <Button
                  className="px-8"
                  onClick={() => handleToggle("enable")}
                  disabled={isLoading || !token.trim()}
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

         {/* Feedback message box */}
         {feedback && feedback.message && (
            <div
               className={`p-4 rounded-lg min-h-[40px] mt-2 ${
                  feedback.status === "success"
                     ? "bg-green-500/20 border border-green-500/50"
                     : "bg-red-500/20 border border-red-500/50"
               }`}
            >
               <p
                  className={
                     feedback.status === "success"
                        ? "text-green-400"
                        : "text-red-400"
                  }
               >
                  {feedback.message}
               </p>
            </div>
         )}
      </div>
   );
};

const FigmaView = () => {
   return <FigmaViewContent />;
};

export default FigmaView;
