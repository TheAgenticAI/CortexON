import {setMessages} from "@/dataStore/messagesSlice";
import {MessageCirclePlus, History} from "lucide-react";
import {useDispatch} from "react-redux";
import {useLocation, useNavigate} from "react-router-dom";
import Logo from "../../assets/CortexON_logo_dark.svg";
import {Button} from "../ui/button";
import {useConversationContext} from "@/contexts/ConversationContext";

const Header = () => {
  const nav = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();
  const {openConversationList} = useConversationContext();

  // Only show conversation button on home page
  const showConversationButton = location.pathname === "/";

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
      <div className="w-full h-full gap-2 items-center px-4">
        <div
          onClick={() => nav("/vault")}
          className={`w-[10%] h-full flex justify-center items-center cursor-pointer border-b-2  hover:border-[#BD24CA] ${
            location.pathname.includes("/vault")
              ? "border-[#BD24CA]"
              : "border-background"
          }`}
        >
          <p className="text-xl font-medium">Vault</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {showConversationButton && (
          <Button
            size="sm"
            variant="outline"
            className="rounded-xl"
            onClick={openConversationList}
            title="View conversation history"
          >
            <History size={20} absoluteStrokeWidth className="mr-2" />
            History
          </Button>
        )}
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
