
import os
from typing import Dict, Union
from core.utils.logger import Logger
from core.server.utils.vault_operations import vault_ops

logger = Logger()


async def get_keys() -> Dict[str, Union[str, int]]:
    """
    Returns all keys from Hashicorp's Vault along with metadata in a structured format.

    Returns:
    dict: A dictionary containing:
        - vault_keys (str): Comma-separated list of vault keys
        - total_count (int): Number of keys found
        - context (str): Description of the data
    
    Example successful response:
        {
            "vault_keys": "key1, key2, key3",
            "total_count": 3,
            "context": "These are the available keys in Hashicorp Vault"
        }
    """
    try:
        vault_ns = os.getenv("VITE_APP_VA_NAMESPACE")
        list = await vault_ops.list_secrets(vault_ns)
        return list
    except Exception as e:
        return f"Error: {e}"
        

async def get_secret(key: str) -> str:
    """
    Returns the secret value for a given key from Hashicorp's Vault.

    Parameters:
        - key (str): The key for which the secret value is requested.

    Returns:
        - str: The secret value.
    """
    if not isinstance(key, str) or not key.strip():
        return "Error: Invalid key provided"
    vault_ns = os.getenv("VITE_APP_VA_NAMESPACE")
    try:
        secret = await vault_ops.get_secret(vault_ns, key)
        return secret
    except Exception as e:
        return f"Error: {e}"

async def main():
    """Main async runner function"""
    try:
        keys_result = await get_keys()
        print("\nVault Keys Result:")
        print(json.dumps(keys_result, indent=2))
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    import json
    import asyncio
    asyncio.run(main())