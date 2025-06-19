import React from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import DefaultView from "@/components/mcp/DefaultView";
import DeleteServerDialog from "@/components/mcp/DeleteServerDialog";
import { useState, useEffect } from "react";
import { Loader2, Trash2 } from "lucide-react";

interface ServiceViewProps {
  service: string | null;
  onServerStatusChange?: () => void;
  onServiceDeleted?: () => void;
}

interface ServerDetails {
  name: string;
  status: string;
  description: string;
  config: {
    command?: string;
    args?: string[];
  };
}

const ServiceView: React.FC<ServiceViewProps> = ({ service, onServerStatusChange, onServiceDeleted }) => {
  const [token, setToken] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [serverDetails, setServerDetails] = useState<ServerDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [feedback, setFeedback] = useState<{
    status: "success" | "error";
    message: string;
  } | null>(null);

  // Fetch server details when service changes
  useEffect(() => {
    if (!service) return;

    const fetchServerDetails = async () => {
      setLoadingDetails(true);
      try {
        const response = await fetch(
          `http://localhost:8081/agent/mcp/servers/${service}`
        );
        if (response.ok) {
          const data = await response.json();
          setServerDetails(data);
        }
      } catch (error) {
        console.error('Failed to fetch server details:', error);
      } finally {
        setLoadingDetails(false);
      }
    };

    fetchServerDetails();
  }, [service]);

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
    if (action === "enable" && !token.trim()) {
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
              ? `${service.charAt(0).toUpperCase() + service.slice(1)} server enabled successfully!`
              : `${service.charAt(0).toUpperCase() + service.slice(1)} server disabled successfully!`,
        });
        
        // Refresh server details
        const updatedResponse = await fetch(
          `http://localhost:8081/agent/mcp/servers/${service}`
        );
        if (updatedResponse.ok) {
          const data = await updatedResponse.json();
          setServerDetails(data);
        }

        // Notify parent to refresh if needed
        if (onServerStatusChange) {
          onServerStatusChange();
        }

        // Clear token on disable
        if (action === "disable") {
          setToken("");
        }
      } else {
        setFeedback({
          status: "error",
          message: `Failed to update ${service.charAt(0).toUpperCase() + service.slice(1)} server. Please try again.`,
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

  const handleDelete = async () => {
    if (!service) return;
    
    setIsDeleting(true);
    try {
      const response = await fetch(
        `http://localhost:8081/agent/mcp/servers/${service}`,
        {
          method: "DELETE",
        }
      );
      
      if (response.ok) {
        // Notify parent components
        if (onServiceDeleted) {
          onServiceDeleted();
        }
        if (onServerStatusChange) {
          onServerStatusChange();
        }
        
        // Close the dialog
        setShowDeleteDialog(false);
      } else {
        const data = await response.json();
        setFeedback({
          status: "error",
          message: data.detail || `Failed to delete ${service} server.`,
        });
      }
    } catch {
      setFeedback({
        status: "error",
        message: "Network error. Please try again.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (!service) {
    return <DefaultView />;
  }

  if (loadingDetails) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const isEnabled = serverDetails?.status === "enabled";

  return (
    <div className="p-8 space-y-8">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
        <h1 className="text-4xl font-bold">{service.charAt(0).toUpperCase() + service.slice(1)} MCP</h1>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowDeleteDialog(true)}
            className="text-red-400 hover:text-red-300 hover:bg-red-400/20"
            title="Delete server"
          >
            <Trash2 className="h-5 w-5" />
          </Button>
        </div>
        
        <p className="text-gray-400">
          {serverDetails?.description || `Configure your ${service.charAt(0).toUpperCase() + service.slice(1)} integration`}
        </p>
        
        {/* Status Badge */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Status:</span>
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            isEnabled 
              ? 'bg-green-500/20 text-green-400 border border-green-500/50' 
              : 'bg-gray-500/20 text-gray-400 border border-gray-500/50'
          }`}>
            {isEnabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
      </div>

      <div className="space-y-4 max-w-xl">
        {!isEnabled && (
        <Input
          type="password"
            placeholder={`Enter your ${service.charAt(0).toUpperCase() + service.slice(1)} API Token`}
          className="bg-gray-800/50 border-gray-700"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        )}
        
        <div className="flex gap-4">
          {!isEnabled ? (
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
          ) : (
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
          )}
        </div>
      </div>

      {/* Feedback message box */}
      {feedback && feedback.message && (
        <div
          className={`p-4 rounded-lg min-h-[40px] mt-2 max-w-xl ${
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

      {/* Server Configuration Details (when enabled) */}
      {isEnabled && serverDetails?.config && (
        <div className="mt-8 p-4 bg-gray-800/30 border border-gray-700 rounded-lg max-w-xl">
          <h3 className="text-lg font-semibold text-gray-300 mb-3">Configuration</h3>
          <div className="space-y-2 text-sm">
            {serverDetails.config.command && (
              <div>
                <span className="text-gray-500">Command:</span>
                <span className="text-gray-300 ml-2">{serverDetails.config.command}</span>
              </div>
            )}
            {serverDetails.config.args && serverDetails.config.args.length > 0 && (
              <div>
                <span className="text-gray-500">Arguments:</span>
                <span className="text-gray-300 ml-2">{serverDetails.config.args.join(' ')}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteServerDialog
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        serverName={service}
        onConfirm={handleDelete}
        isDeleting={isDeleting}
      />
    </div>
  );
};

export default ServiceView; 