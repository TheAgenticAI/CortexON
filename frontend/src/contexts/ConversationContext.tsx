import {createContext, useContext, useState, ReactNode} from "react";

interface ConversationContextType {
  isOpen: boolean;
  openConversationList: () => void;
  closeConversationList: () => void;
}

const ConversationContext = createContext<ConversationContextType | undefined>(
  undefined
);

export const ConversationProvider = ({children}: {children: ReactNode}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <ConversationContext.Provider
      value={{
        isOpen,
        openConversationList: () => setIsOpen(true),
        closeConversationList: () => setIsOpen(false),
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
};

export const useConversationContext = () => {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error(
      "useConversationContext must be used within ConversationProvider"
    );
  }
  return context;
};

