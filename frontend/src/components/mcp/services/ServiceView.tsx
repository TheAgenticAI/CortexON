import React from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import DefaultView from "@/components/mcp/DefaultView";
import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";

interface ServiceViewProps {
  service: string | null;
}

const ServiceView: React.FC<ServiceViewProps> = ({ service }) => {
  const [token, setToken] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<{
    status: "success" | "error";
    message: string;
  } | null>(null);

  // Clear feedback message after 2 seconds whenever it changes
  useEffect(() => {
    if (feedback) {
      const timer = setTimeout(() => {
        setFeedback(null);
      }, 2000);

      // Cleanup timeout on component unmount or when feedback changes
      return () => clearTimeout(timer);
    }
  }, [feedback]);

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
            server_name: service,
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
              ? `${service.charAt(0).toUpperCase() + service.slice(1)} token enabled successfully!`
              : `${service.charAt(0).toUpperCase() + service.slice(1)} token disabled successfully!`,
        });
      } else {
        setFeedback({
          status: "error",
          message: `Failed to update ${service.charAt(0).toUpperCase() + service.slice(1)} token. Please try again.`,
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

  if (!service) {
    return <DefaultView />;
  }

  return (
    <div className="p-8 space-y-8">
      <div className="space-y-4">
        <h1 className="text-4xl font-bold">{service.charAt(0).toUpperCase() + service.slice(1)} MCP</h1>
        <p className="text-gray-400">
        Configure your {service.charAt(0).toUpperCase() + service.slice(1)} Personal Access Token to enable {service.charAt(0).toUpperCase() + service.slice(1)} mcp integration
        </p>
      </div>

      <div className="space-y-4 max-w-xl">
        <Input
          type="password"
          placeholder={`Enter your ${service.charAt(0).toUpperCase() + service.slice(1)} Token`}
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

export default ServiceView; 