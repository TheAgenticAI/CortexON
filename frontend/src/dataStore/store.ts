import vaultApi from "@/services/vaultApi";
import modelPreferenceApi from "@/services/modelPreferenceApi";
import {configureStore} from "@reduxjs/toolkit";
import messagesSlice from "./messagesSlice";
import modelPreferenceSlice from "./modelPreferenceSlice";

export const store = configureStore({
  reducer: {
    [messagesSlice.name]: messagesSlice.reducer,
    [vaultApi.reducerPath]: vaultApi.reducer,
    [modelPreferenceSlice.name]: modelPreferenceSlice.reducer,
    [modelPreferenceApi.reducerPath]: modelPreferenceApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(vaultApi.middleware, modelPreferenceApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
