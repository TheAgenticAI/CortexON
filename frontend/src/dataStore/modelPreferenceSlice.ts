import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface ModelPreferenceState {
  preference: "Anthropic" | "OpenAI";
}

const initialState: ModelPreferenceState = {
  preference: "Anthropic",
};

const modelPreferenceSlice = createSlice({
  name: "modelPreference",
  initialState,
  reducers: {
    setModelPreference: (state, action: PayloadAction<"Anthropic" | "OpenAI">) => {
      state.preference = action.payload;
    },
  },
});

export const { setModelPreference } = modelPreferenceSlice.actions;
export default modelPreferenceSlice; 