import {fetchBaseQuery} from "@reduxjs/toolkit/query/react";

const {VITE_APP_API_BASE_URL} = import.meta.env;

export const platformAuthConfig = () => {
  return {
    baseQuery: fetchBaseQuery({
      baseUrl: `${VITE_APP_API_BASE_URL}/api/v1`,
      credentials: "include",
      prepareHeaders: (headers) => {
        return headers;
      },
    }),
    keepUnusedDataFor: 20,
    refetchOnMountOrArgChange: true,
  };
};
