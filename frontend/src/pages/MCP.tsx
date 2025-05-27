import {ScrollArea} from "@/components/ui/scroll-area";
import Sidebar from "@/components/mcp/Sidebar";
import DefaultView from "@/components/mcp/DefaultView";

export const MCP = () => {
  return (
    <div className="flex h-[92vh]">
      <Sidebar />
      <div className="flex-1 p-8 space-y-6">
        {/* <div className="space-y-2">
          <h1 className="text-3xl font-bold">MCP</h1>
          <p className="text-muted-foreground">
            Monitor and control your processes.
          </p>
        </div> */}
        <ScrollArea className="h-[calc(92vh-8rem)]">
          <DefaultView />
        </ScrollArea>
      </div>
    </div>
  );
};

export default MCP; 