import vaultApi from "@/services/vaultApi";
import {configureStore} from "@reduxjs/toolkit";
import messagesSlice from "./messagesSlice";
export const store = configureStore({
  reducer: {
    [messagesSlice.name]: messagesSlice.reducer,
    [vaultApi.reducerPath]: vaultApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(vaultApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
