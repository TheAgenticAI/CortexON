import {setMessages} from "@/dataStore/messagesSlice";
import {MessageCirclePlus} from "lucide-react";
import {useDispatch} from "react-redux";
import {useLocation, useNavigate} from "react-router-dom";
import Logo from "../../assets/CortexON_logo_dark.svg";
import {Button} from "../ui/button";
import ModelToggle from "../ui/ModelToggle";

const Header = () => {
  const nav = useNavigate();
  const location = useLocation().pathname;
  const dispatch = useDispatch();

  return (
    <div className="h-[8vh] border-b-2 flex justify-between items-center px-8">
      <div className="flex items-center gap-6">
        <div
          className="cursor-pointer w-[140px]"
          onClick={() => {
            dispatch(setMessages([]));
            nav("/");
          }}
        >
          <img src={Logo} alt="Logo" className="w-full" />
        </div>
        
        <div
          onClick={() => nav("/vault")}
          className={`h-full flex justify-center items-center cursor-pointer border-b-2 -mb-[2px] px-4 hover:border-[#BD24CA] ${
            location.includes("/vault")
              ? "border-[#BD24CA]"
              : "border-background"
          }`}
        >
          <p className="text-xl font-medium">Vault</p>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        {/* Model Toggle Button - Smaller size */}
        <div className="scale-75 hover:opacity-90 transition-opacity cursor-pointer">
          <ModelToggle />
        </div>
        
        <Button
          size="sm"
          className="rounded-xl"
          onClick={() => {
            dispatch(setMessages([]));
            nav("/");
          }}
        >
          <MessageCirclePlus size={20} absoluteStrokeWidth />
          New Chat
        </Button>
      </div>
    </div>
  );
};

export default Header;
