import asyncio
from threading import Thread
import time
from typing import Dict, Any, List
import httpx
from httpx._models import Response
import os

from core.server.utils.vault_exceptions import TokenException, InternalError, NotFoundError
from core.server.utils.server_logger import logger

config = {
    "VA_TOKEN": os.getenv("VA_TOKEN", ""),
    "VA_URL": os.getenv("VA_URL", "http://localhost:8200"),
    "VA_TTL": os.getenv("VA_TTL", "24h"),
    "VA_TOKEN_REFRESH_SECONDS": os.getenv("VA_TOKEN_REFRESH_SECONDS", "43200"),  # 12 hours default
}

class VaultOperations:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    async def vault_request(self, method: str, path: str, data: dict = {}, ns: str = "") -> Response:
        """
        Make a request to HashiCorp Vault.
        """
        token = self.config["VA_TOKEN"]
        url = f"{str(self.config['VA_URL']).rstrip('/')}/v1{path}"
        headers = {"X-Vault-Token": token, "X-Vault-Namespace": f"admin/{ns}".rstrip("/")}
        
        async with httpx.AsyncClient(timeout=10) as client:
            req = client.build_request(method=method, url=url, headers=headers, json=data)
            resp = await client.send(req)
            self.logger.info(f"{method} to {path} - {resp.status_code}")
            return resp

        return Response(status_code=500)

    async def renew_token(self):
        """
        Renews the Vault token.        
        """
        self.logger.debug("Renewing token")
        data = {"increment": self.config["VA_TTL"]}
        resp = await self.vault_request(method="POST", path="/auth/token/renew-self", data=data)
        if resp.status_code != 200:
            raise TokenException("Failed to renew token")

        token = resp.json()["auth"]["client_token"]
        self.config["VA_TOKEN"] = token

    async def init_vault(self):
        """
        Initializes the Vault instance. Creates a new token and starts the token refresh thread.
        """
        self.logger.debug("Creating new token")
        resp = await self.vault_request("POST", "/auth/token/create", data={"no_parent": True, "ttl": self.config["VA_TTL"]})
        self.logger.debug(resp.content.decode("utf-8"))
        if resp.status_code != 200:
            raise InternalError("Failed to initialize vault")
        self.config["VA_TOKEN"] = resp.json()["auth"]["client_token"]

        vt = VaultTokenRefresh(self)
        vt.start()

    async def get_secret(self, ns: str, secret_key: str) -> Dict[str, Any]:
        """
        Get a secret from the Vault.
        """
        resp = await self.vault_request(method="GET", path=f"/secretMount/{secret_key}", ns=ns)

        if resp.status_code == 404:
            self.logger.debug(f"get_secret resp: {resp.content}")
            raise NotFoundError(f"Secret {secret_key} not found")

        if resp.status_code != 200:
            self.logger.debug(f"get_secret resp: {resp.content}")
            raise InternalError("Failed to get secret")

        secret_data = resp.json()
        secret = secret_data.get("data")
        return {"secret": secret, "success_status": True}

    async def set_secret(self, ns: str, secret_key: str, secret_value: str):
        """
        Set a secret in the Vault.
        """
        body = {secret_key: secret_value}
        resp = await self.vault_request(method="POST", path=f"/secretMount/{secret_key}", 
                                      data=body, ns=ns)
        self.logger.debug(f"set_secret resp: {resp.content}")

        if resp.status_code not in [200, 204]:
            self.logger.error(f"Vault Error: {resp.content}")
            raise InternalError("Failed to store secret in Vault")
        
        return True


    async def list_secrets(self, ns: str) -> List[str]:
        """
        Lists secrets from the Vault for a given namespace.
        """
        resp = await self.vault_request(method="LIST", path=f"/secretMount", ns=ns)

        if resp.status_code > 300:
            self.logger.debug(f"list_secrets resp: {resp.content}")
            self.logger.debug("Could not list secrets")
            return []
        return resp.json()["data"]["keys"]

    async def delete_secret(self, secret_key: str, ns: str) -> bool:
        """
        Deletes a secret from the Vault.
        """
        resp = await self.vault_request(method="DELETE", path=f"/secretMount/{secret_key}", ns=ns)
        self.logger.debug(f"delete_secret resp - status: {resp.status_code} content: {resp.content}")
        return resp.status_code == 204

    async def setup_user(self, ns: str):
        """
        Sets up a new user / namespace in the Vault.
        """
        resp = await self.vault_request("POST", path=f"/sys/namespaces/{ns}")
        if resp.status_code != 200:
            self.logger.debug(resp.content)
            raise InternalError(f"Failed to create namespace {ns}")

        body = {"type": "kv"}
        resp = await self.vault_request("POST", path=f"/sys/mounts/secretMount", data=body, ns=ns)
        if resp.status_code != 204:
            raise InternalError(f"Failed to setup mount for namespace {ns}")
        
    async def list_ns(self):
        """
        Lists all namespaces in the Vault.
        """
        resp = await self.vault_request("LIST", "/sys/namespaces")
        if resp.status_code != 200:
            raise InternalError("Failed to list namespaces")
        return resp.json()["data"]["keys"]

class VaultTokenRefresh(Thread):
    """
    Thread to refresh the Vault token at regular intervals according to the TTL.
    """
    def __init__(self, vault_ops: VaultOperations) -> None:
        super().__init__(daemon=True)
        self.token_history = []
        self.start_time = 0
        self.vault_ops = vault_ops
        self.time_interval = int(vault_ops.config["VA_TOKEN_REFRESH_SECONDS"])

    def run(self) -> None:
        self.start_time = time.time()

        while True:
            curr_time = time.time()
            if curr_time - self.start_time >= self.time_interval:
                asyncio.run(self.vault_ops.renew_token())
                self.start_time = time.time()

            time.sleep(5)

vault_ops = VaultOperations(config, logger)
