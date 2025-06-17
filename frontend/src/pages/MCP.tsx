import { ScrollArea } from "@/components/ui/scroll-area";
import Sidebar from "@/components/mcp/Sidebar";
import ServiceView from "@/components/mcp/services/ServiceView";
import { useState, useRef } from "react";

export const MCP = () => {
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleServerStatusChange = () => {
    // Increment the key to force re-render of Sidebar
    setRefreshKey(prev => prev + 1);
  };

  const handleServiceDeleted = () => {
    // Reset selected service to null to show default view
    setSelectedService(null);
    // Also refresh the sidebar
    handleServerStatusChange();
  };

  return (
    <div className="flex h-[92vh]">
      <Sidebar 
        key={refreshKey}
        onServiceSelect={setSelectedService} 
      />
      <div className="flex-1">
        <ScrollArea className="h-full">
          <ServiceView 
            service={selectedService} 
            onServerStatusChange={handleServerStatusChange}
            onServiceDeleted={handleServiceDeleted}
          />
        </ScrollArea>
      </div>
    </div>
  );
};

export default MCP; 