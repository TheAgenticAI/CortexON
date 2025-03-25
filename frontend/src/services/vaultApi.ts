import {
  AddSecretRequest,
  AddSecretResponse,
  DeleteSecretResponse,
  GetVaultResponse,
  SecretRequest,
  SecretResponse,
} from "@/types/vaultTypes";
import {createApi, FetchArgs} from "@reduxjs/toolkit/query/react";
import {platformAuthConfig} from "./platformConfig";

export type TagTypes = "Vault";

const vaultApi = createApi({
  reducerPath: "vaultApi",
  ...platformAuthConfig(),
  tagTypes: ["Vault", "VaultList"],
  endpoints: (builder) => ({
    getSecrets: builder.query<GetVaultResponse, string>({
      query: (namespace: string): FetchArgs => ({
        url: `/vault/secrets?namespace=${namespace}`,
        method: "GET",
      }),
      providesTags: ["VaultList"],
    }),

    getSecret: builder.query<SecretResponse, SecretRequest>({
      query: (config): FetchArgs => ({
        url: `/vault/secrets/${config.secret_key}?namespace=${config.namespace}`,
        method: "GET",
      }),
      providesTags: ["Vault"],
    }),

    addSecret: builder.mutation<AddSecretResponse, AddSecretRequest>({
      query: (config): FetchArgs => ({
        url: `/vault/secrets/create`,
        method: "POST",
        body: config,
      }),
      invalidatesTags: ["Vault", "VaultList"],
    }),

    deleteSecret: builder.mutation<DeleteSecretResponse, SecretRequest>({
      query: (config): FetchArgs => ({
        url: `/vault/secrets/${config.secret_key}?namespace=${config.namespace}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Vault", "VaultList"],
    }),
  }),
});

export const {
  useGetSecretsQuery,
  useAddSecretMutation,
  useDeleteSecretMutation,
  useLazyGetSecretQuery,
} = vaultApi;

export default vaultApi;
