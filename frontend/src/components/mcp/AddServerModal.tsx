import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Plus, X } from 'lucide-react';

interface AddServerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onServerAdded: () => void;
}

const AddServerModal: React.FC<AddServerModalProps> = ({ isOpen, onClose, onServerAdded }) => {
  const [serverName, setServerName] = useState('');
  const [command, setCommand] = useState('');
  const [args, setArgs] = useState<string[]>(['']);
  const [description, setDescription] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAddArg = () => {
    setArgs([...args, '']);
  };

  const handleRemoveArg = (index: number) => {
    setArgs(args.filter((_, i) => i !== index));
  };

  const handleArgChange = (index: number, value: string) => {
    const newArgs = [...args];
    newArgs[index] = value;
    setArgs(newArgs);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    // Validate required fields
    if (!serverName || !command || !description || !secretKey) {
      setError('All fields except API key are required');
      setIsLoading(false);
      return;
    }

    // Filter out empty args
    const filteredArgs = args.filter(arg => arg.trim() !== '');

    try {
      const serverConfig = {
        command,
        args: filteredArgs,
        env: apiKey ? { [secretKey]: apiKey } : {},
        description,
        secret_key: secretKey
      };

      const response = await fetch(
        `http://localhost:8081/agent/mcp/servers/add?server_name=${encodeURIComponent(serverName)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(serverConfig),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to add server');
      }

      // Reset form
      setServerName('');
      setCommand('');
      setArgs(['']);
      setDescription('');
      setSecretKey('');
      setApiKey('');
      
      onServerAdded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add server');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] bg-gray-900 border-gray-700">
        <DialogHeader>
          <DialogTitle className="text-white">Add MCP Server</DialogTitle>
          <DialogDescription className="text-gray-400">
            Configure a new Model Context Protocol server
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="serverName" className="text-white">Server Name</Label>
            <Input
              id="serverName"
              value={serverName}
              onChange={(e) => setServerName(e.target.value)}
              placeholder="e.g., github"
              className="bg-gray-800/50 border-gray-700 text-white"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="command" className="text-white">Command</Label>
            <Input
              id="command"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="e.g., npx"
              className="bg-gray-800/50 border-gray-700 text-white"
              required
            />
          </div>

          <div className="space-y-2">
            <Label className="text-white">Arguments</Label>
            {args.map((arg, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  value={arg}
                  onChange={(e) => handleArgChange(index, e.target.value)}
                  placeholder={`Argument ${index + 1}`}
                  className="bg-gray-800/50 border-gray-700 text-white"
                />
                {args.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveArg(index)}
                    className="text-red-400 hover:text-red-300"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddArg}
              className="mt-2 border-gray-600 text-gray-300 hover:text-white"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Argument
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description" className="text-white">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this server does"
              className="bg-gray-800/50 border-gray-700 text-white"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="secretKey" className="text-white">Secret Key Name</Label>
            <Input
              id="secretKey"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              placeholder="e.g., GITHUB_PERSONAL_ACCESS_TOKEN"
              className="bg-gray-800/50 border-gray-700 text-white"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="apiKey" className="text-white">
              API Key (Optional)
              <span className="text-sm text-gray-400 ml-2">
                Leave empty to add as disabled
              </span>
            </Label>
            <Input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Your API key"
              className="bg-gray-800/50 border-gray-700 text-white"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="border-gray-600 text-gray-300 hover:text-white"
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add Server'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default AddServerModal; 