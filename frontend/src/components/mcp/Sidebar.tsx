import { useEffect, useState } from "react";
import { mcpService, MCPServer } from "@/services/mcpService";
import { Github, Map, Figma, Bot } from 'lucide-react';

interface SidebarProps {
   onServiceSelect: (service: string) => void;
}

const services = [
  { name: 'GitHub', icon: Github },
  { name: 'Google Maps', icon: Map },
  { name: 'Figma', icon: Figma },
  { name: 'Claude', icon: Bot },
];

const Sidebar = ({ onServiceSelect }: SidebarProps) => {
   const [servers, setServers] = useState<MCPServer[]>([]);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState("");

   useEffect(() => {
      const fetchServers = async () => {
         try {
            const data = await mcpService.getServers();
            setServers(data);
            setLoading(false);
         } catch (err) {
            setError("Failed to load servers");
            setLoading(false);
         }
      };
      fetchServers();
   }, []);

   return (
      <div className="w-80 bg-gray-800/50 backdrop-blur-sm border-r border-gray-600/30 p-6 flex flex-col gap-4">
         {loading && <div className="text-gray-400">Loading...</div>}
         {error && <div className="text-red-400">{error}</div>}
         {!loading &&
            !error &&
            servers.map((server) => {
               return (
                  <button
                     key={server.name}
                     onClick={() =>
                        onServiceSelect(
                           server.name.charAt(0).toUpperCase() +
                              server.name.slice(1).replace("_", " ")
                        )
                     }
                     className="flex items-center gap-3 p-4 bg-gray-700/30 border border-gray-600/50 rounded-xl text-white hover:bg-gray-600/40 hover:border-cyan-400/50 transition-all duration-200 hover:scale-105 group"
                  >
                     <span className="font-medium">
                        {server.name.charAt(0).toUpperCase() +
                           server.name.slice(1).replace("_", " ")}
                     </span>
                  </button>
               );
            })}
      </div>
   );
};

export default Sidebar;
