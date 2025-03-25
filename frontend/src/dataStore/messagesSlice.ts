import {Message} from "@/types/chatTypes";
import {createSlice} from "@reduxjs/toolkit";

export const initialState: {
  messages: Message[];
} = {
  messages: [],
};

export const messagesSlice = createSlice({
  name: "messagesState",
  initialState,
  reducers: {
    setMessages: (state, action) => {
      state.messages = action.payload;
    },
  },
});

export const {setMessages} = messagesSlice.actions;

export default messagesSlice;
