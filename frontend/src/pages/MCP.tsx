import { ScrollArea } from "@/components/ui/scroll-area";
import Sidebar from "@/components/mcp/Sidebar";
import DefaultView from "@/components/mcp/DefaultView";
import GithubView from "@/components/mcp/services/GithubView";
import GoogleMapsView from "@/components/mcp/services/GoogleMapsView";
import FigmaView from "@/components/mcp/services/FigmaView";
import ClaudeView from "@/components/mcp/services/ClaudeView";
import { useState } from "react";

export const MCP = () => {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const renderContent = () => {
    switch (selectedService) {
      case "github":
        return <GithubView />;
      case "google-maps":
        return <GoogleMapsView />;
      case "figma":
        return <FigmaView />;
      case "claude":
        return <ClaudeView />;
      default:
        return <DefaultView />;
    }
  };

  return (
    <div className="flex h-[92vh]">
      <Sidebar onServiceSelect={setSelectedService} />
      <div className="flex-1">
        <ScrollArea className="h-full">
          {renderContent()}
        </ScrollArea>
      </div>
    </div>
  );
};

export default MCP; 