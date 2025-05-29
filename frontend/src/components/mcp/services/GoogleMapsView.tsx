import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Loader2 } from "lucide-react";

const GoogleMapsViewContent = () => {
   const [apiKey, setApiKey] = useState("");
   const [isLoading, setIsLoading] = useState(false);
   const [feedback, setFeedback] = useState<{
      status: "success" | "error";
      message: string;
   } | null>(null);

   const handleToggle = async (action: "enable" | "disable") => {
      if (!apiKey.trim()) {
         setFeedback({ status: "error", message: "Please enter an API key." });
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
                  server_name: "google-maps",
                  server_secret: apiKey,
                  action,
               }),
            }
         );
         if (response.ok) {
            setFeedback({
               status: "success",
               message:
                  action === "enable"
                     ? "Google Maps API key enabled successfully!"
                     : "Google Maps API key disabled successfully!",
            });
         } else {
            setFeedback({
               status: "error",
               message:
                  "Failed to update Google Maps API key. Please try again.",
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
                  disabled={isLoading || !apiKey.trim()}
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

const GoogleMapsView = () => {
   return <GoogleMapsViewContent />;
};

export default GoogleMapsView;
