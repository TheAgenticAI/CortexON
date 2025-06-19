import React, { useEffect, useState } from 'react';
import { Github, Map, Figma, Bot, Plus, Trash2 } from 'lucide-react';
import AddServerModal from './AddServerModal';
import DeleteServerDialog from './DeleteServerDialog';

interface SidebarProps {
  onServiceSelect: (service: string) => void;
}

interface Server {
  name: string;
  description: string;
  status: string;
}

const Sidebar = ({ onServiceSelect }: SidebarProps) => {
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [deleteDialogState, setDeleteDialogState] = useState<{
    isOpen: boolean;
    serverName: string;
  }>({ isOpen: false, serverName: '' });
  const [isDeleting, setIsDeleting] = useState(false);

    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:8081/agent/mcp/servers');
        const data = await response.json();
        setServers(data);
      } catch (error) {
        console.error('API call failed:', error);
      } finally {
        setLoading(false);
      }
    };

  useEffect(() => {
    fetchData();
  }, []);

  const handleServerAdded = () => {
    // Refresh the servers list
    fetchData();
  };

  const handleDeleteClick = (e: React.MouseEvent, serverName: string) => {
    e.stopPropagation(); // Prevent triggering the server selection
    setDeleteDialogState({ isOpen: true, serverName });
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const response = await fetch(
        `http://localhost:8081/agent/mcp/servers/${deleteDialogState.serverName}`,
        {
          method: "DELETE",
        }
      );
      
      if (response.ok) {
        // Refresh the servers list
        fetchData();
        // Close the dialog
        setDeleteDialogState({ isOpen: false, serverName: '' });
      }
    } catch (error) {
      console.error('Failed to delete server:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
    <div className="w-80 bg-gray-800/50 backdrop-blur-sm border-r border-gray-600/30 p-6 flex flex-col gap-4">
        {/* Add Server Button */}
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center justify-center gap-3 p-4 bg-purple-600/20 border border-purple-500/50 rounded-xl text-white hover:bg-purple-600/30 hover:border-purple-400 transition-all duration-200 hover:scale-105 group"
        >
          <Plus className="w-5 h-5 text-purple-400 group-hover:text-purple-300 transition-colors" />
          <span className="font-medium text-purple-300 group-hover:text-purple-200">Add New Server</span>
        </button>

        {/* Divider */}
        <div className="border-t border-gray-700/50 my-2" />

        {/* Server List */}
      {servers.map((server) => {
        const IconComponent = Bot;
        return (
          <button
            key={server.name}
            onClick={() => onServiceSelect(server.name)}
              className="relative flex items-center gap-3 p-4 bg-gray-700/30 border border-gray-600/50 rounded-xl text-white hover:bg-gray-600/40 hover:border-purple-400/50 transition-all duration-200 hover:scale-105 group"
          >
            <IconComponent className="w-5 h-5 text-gray-300 group-hover:text-purple-400 transition-colors" />
              <span className="font-medium flex-1 text-left">
                {server.name.charAt(0).toUpperCase() + server.name.slice(1)}
              </span>
              
              {/* Delete button - visible on hover */}
              <button
                onClick={(e) => handleDeleteClick(e, server.name)}
                className="absolute right-2 opacity-0 group-hover:opacity-100 p-2 rounded-lg bg-gray-800/50 hover:bg-red-500/20 transition-all duration-200"
                title={`Delete ${server.name}`}
              >
                <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-400" />
              </button>
          </button>
        );
      })}
    </div>

      {/* Add Server Modal */}
      <AddServerModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onServerAdded={handleServerAdded}
      />

      {/* Delete Server Dialog */}
      <DeleteServerDialog
        isOpen={deleteDialogState.isOpen}
        onClose={() => setDeleteDialogState({ isOpen: false, serverName: '' })}
        serverName={deleteDialogState.serverName}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </>
  );
};

export default Sidebar; 