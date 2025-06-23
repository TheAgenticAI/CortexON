import { ScrollArea } from "@/components/ui/scroll-area";
import Sidebar from "@/components/mcp/Sidebar";
import ServiceView from "@/components/mcp/services/ServiceView";
import { useState } from "react";

export const MCP = () => {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  return (
    <div className="flex h-[92vh]">
      <Sidebar onServiceSelect={setSelectedService} />
      <div className="flex-1">
        <ScrollArea className="h-full">
          <ServiceView service={selectedService} />
        </ScrollArea>
      </div>
    </div>
  );
};

export default MCP; 