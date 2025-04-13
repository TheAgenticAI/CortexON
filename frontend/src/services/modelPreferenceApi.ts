import { createApi } from "@reduxjs/toolkit/query/react";
import { fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// Get the base URL from environment variable or use a default
const CORTEX_ON_API_URL = import.meta.env.VITE_CORTEX_ON_API_URL || "http://localhost:8081";

const modelPreferenceApi = createApi({
  reducerPath: "modelPreferenceApi",
  baseQuery: fetchBaseQuery({
    baseUrl: CORTEX_ON_API_URL,
  }),
  endpoints: (builder) => ({
    setModelPreference: builder.mutation<{ message: string }, string>({
      query: (model) => ({
        url: `/set_model_preference?model=${model}`,
        method: "GET",
      }),
    }),
  }),
});

export const { useSetModelPreferenceMutation } = modelPreferenceApi;
export default modelPreferenceApi; 