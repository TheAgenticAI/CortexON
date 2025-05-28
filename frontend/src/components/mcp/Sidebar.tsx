import React, { useEffect, useState } from 'react';
import { Github, Map, Figma, Bot } from 'lucide-react';

interface SidebarProps {
  onServiceSelect: (service: string) => void;
}

interface Server {
  name: string;
  description: string;
  status: string;
}

const getServiceIcon = (name: string) => {
  switch(name.toLowerCase()) {
    case 'github':
      return Github;
    case 'google-maps':
      return Map;
    default:
      return Bot;
  }
};

const Sidebar = ({ onServiceSelect }: SidebarProps) => {
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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

    fetchData();
  }, []);

  return (
    <div className="w-80 bg-gray-800/50 backdrop-blur-sm border-r border-gray-600/30 p-6 flex flex-col gap-4">
      {servers.map((server) => {
        const IconComponent = getServiceIcon(server.name);
        return (
          <button
            key={server.name}
            onClick={() => onServiceSelect(server.name)}
            className="flex items-center gap-3 p-4 bg-gray-700/30 border border-gray-600/50 rounded-xl text-white hover:bg-gray-600/40 hover:border-purple-400/50 transition-all duration-200 hover:scale-105 group"
          >
            <IconComponent className="w-5 h-5 text-gray-300 group-hover:text-purple-400 transition-colors" />
            <span className="font-medium">{server.name}</span>
          </button>
        );
      })}
    </div>
  );
};

export default Sidebar; 