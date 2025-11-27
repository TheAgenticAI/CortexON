import {Message} from "@/types/chatTypes";
import {createSlice} from "@reduxjs/toolkit";
import {loadCurrentConversation} from "./persistenceMiddleware";

// Load messages from localStorage on initialization
const loadInitialMessages = (): Message[] => {
  try {
    const saved = loadCurrentConversation();
    return saved.length > 0 ? saved : [];
  } catch (error) {
    console.error("Error loading initial messages:", error);
    return [];
  }
};

export const initialState: {
  messages: Message[];
} = {
  messages: loadInitialMessages(),
};

export const messagesSlice = createSlice({
  name: "messagesState",
  initialState,
  reducers: {
    setMessages: (state, action) => {
      state.messages = action.payload;
    },
    clearMessages: (state) => {
      state.messages = [];
    },
  },
});

export const {setMessages, clearMessages} = messagesSlice.actions;

export default messagesSlice;
