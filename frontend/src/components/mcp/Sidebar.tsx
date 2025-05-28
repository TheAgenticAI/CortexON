import React from 'react';
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
  return (
    <div className="w-80 bg-gray-800/50 backdrop-blur-sm border-r border-gray-600/30 p-6 flex flex-col gap-4">
      {services.map((service) => {
        const IconComponent = service.icon;
        return (
          <button
            key={service.name}
            onClick={() => onServiceSelect(service.name)}
            className="flex items-center gap-3 p-4 bg-gray-700/30 border border-gray-600/50 rounded-xl text-white hover:bg-gray-600/40 hover:border-purple-400/50 transition-all duration-200 hover:scale-105 group"
          >
            <IconComponent className="w-5 h-5 text-gray-300 group-hover:text-purple-400 transition-colors" />
            <span className="font-medium">{service.name}</span>
          </button>
        );
      })}
    </div>
  );
};

export default Sidebar; 