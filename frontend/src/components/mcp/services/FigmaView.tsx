import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const FigmaView = () => {
  return (
    <div className="p-8 space-y-8">
      <div className="space-y-4">
        <h1 className="text-4xl font-bold">Figma MCP</h1>
        <p className="text-gray-400">
          Some details, how to configure token etc
        </p>
      </div>
      
      <div className="space-y-4 max-w-xl">
        <Input
          type="password"
          placeholder="Enter your Personal Access Token"
          className="bg-gray-800/50 border-gray-700"
        />
        <Button className="px-8">Enable</Button>
      </div>
    </div>
  );
};

export default FigmaView; 