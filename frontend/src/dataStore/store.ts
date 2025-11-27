import vaultApi from "@/services/vaultApi";
import {configureStore} from "@reduxjs/toolkit";
import messagesSlice from "./messagesSlice";
import {persistenceMiddleware} from "./persistenceMiddleware";

export const store = configureStore({
  reducer: {
    [messagesSlice.name]: messagesSlice.reducer,
    [vaultApi.reducerPath]: vaultApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(vaultApi.middleware, persistenceMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
