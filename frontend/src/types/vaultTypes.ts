export type TSecret = {
  website: string;
  secrets: {
    id: string;
    username: string;
    password: string;
  }[];
};

export type GetVaultResponse = {
  status: number;
  message: string[];
};

export type SecretResponse = {
  status: number;
  message: Record<string, unknown>;
};

export type AddSecretRequest = {
  namespace: string;
  secrets: Record<string, string>;
};

export type SecretRequest = {
  namespace: string;
  secret_key: string;
};

export type DeleteSecretResponse = {
  status: number;
  message: {
    status: string;
  };
};

export type AddSecretResponse = {
  status: number;
  message: {
    status: string;
    details: Record<string, string>;
  };
};
