import {RootState} from "@/dataStore/store";
import {useState} from "react";
import {useSelector} from "react-redux";
import ChatList from "./ChatList";
import Landing from "./Landing";

const Chat = () => {
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const messages = useSelector(
    (state: RootState) => state.messagesState.messages
  );

  return (
    <div className="flex justify-center items-center h-[92vh] overflow-auto scrollbar-thin">
      {messages.length === 0 ? (
        <Landing isLoading={isLoading} setIsLoading={setIsLoading} />
      ) : (
        <ChatList isLoading={isLoading} setIsLoading={setIsLoading} />
      )}
    </div>
  );
};

export default Chat;
