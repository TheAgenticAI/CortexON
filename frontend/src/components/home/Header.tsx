import {setMessages} from "@/dataStore/messagesSlice";
import {MessageCirclePlus} from "lucide-react";
import {useDispatch} from "react-redux";
import {useLocation, useNavigate} from "react-router-dom";
import Logo from "../../assets/CortexON_logo_dark.svg";
import {Button} from "../ui/button";

const Header = () => {
  const nav = useNavigate();
  const location = useLocation().pathname;
  const dispatch = useDispatch();

  return (
    <div className="h-[8vh] border-b-2 flex justify-between items-center px-8">
      <div
        className="w-[12%]"
        onClick={() => {
          dispatch(setMessages([]));
          nav("/");
        }}
      >
        <img src={Logo} alt="Logo" />
      </div>
      <div className="w-full h-full gap-2 items-center px-4 flex">
        <div
          onClick={() => nav("/vault")}
          className={`w-[10%] h-full flex justify-center items-center cursor-pointer border-b-2  hover:border-[#BD24CA] ${
            location.includes("/vault")
              ? "border-[#BD24CA]"
              : "border-background"
          }`}
        >
          <p className="text-xl font-medium">Vault</p>
        </div>
        
        <div
          onClick={() => nav("/mcp")}
          className={`w-[10%] h-full flex justify-center items-center cursor-pointer border-b-2  hover:border-[#BD24CA] ${
            location.includes("/mcp")
              ? "border-[#BD24CA]"
              : "border-background"
          }`}
        >
          <p className="text-xl font-medium">MCP</p>
        </div>
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
  );
};

export default Header;
