import os
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Body, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from core.server.utils.vault_operations import vault_ops
from core.server.utils.vault_exceptions import InternalError

from core.utils.logger import Logger

logger = Logger()

router = APIRouter(prefix="/vault", tags=["Vault"])
security = HTTPBearer()


class SecretCreateRequest(BaseModel):
    namespace: str
    secrets: Dict[str, str]  # Accept multiple key/value pairs


class NamespaceRequest(BaseModel):
    namespace: str = Field(..., description="Namespace for the vault operations")


@router.get("/secrets")
async def list_secrets(
    namespace: str = Query(..., description="Namespace for the vault operations")
):
    try:
        if namespace:
            secrets = await vault_ops.list_secrets(namespace)
            return {"status": 200, "message": secrets}
        else:
            raise HTTPException(status_code=400, detail="Missing namespace")
    except Exception as e:
        logger.error(f"Error listing secrets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list secrets: {str(e)}")


@router.get("/secrets/{secret_key}")
async def get_secret(
    secret_key: str,
    namespace: str = Query(..., description="Namespace for the vault operations"),
):
    """
    Retrieve a secret for a given secret_key from the user's namespace.
    """
    try:
        if not namespace:
            return JSONResponse(
                status_code=400,
                content={"status": 400, "message": "Invalid namespace (vault_ns)"},
            )

        logger.info(f"Getting secrets for : {namespace}")
        secret = await vault_ops.get_secret(namespace, secret_key)
        return {"status": 200, "message": secret}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": 500, "message": f"Failed to get secret: {str(e)}"},
        )


@router.post("/secrets/create")
async def create_secret(
    request: SecretCreateRequest,
):
    """Create multiple secrets in user's namespace"""
    try:
        namespace = request.namespace

        if not namespace:
            return JSONResponse(
                status_code=400, content={"status": 400, "message": "Invalid namespace"}
            )

        results = {}
        for key, value in request.secrets.items():
            await vault_ops.set_secret(ns=namespace, secret_key=key, secret_value=value)
            results[key] = "created"

        return {
            "status": 200,
            "message": {"status": "Secrets created", "details": results},
        }

    except InternalError as e:
        return JSONResponse(status_code=500, content={"status": 500, "message": str(e)})
    except Exception as e:
        logger.error(f"Secret creation error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": 500, "message": "Failed to create secrets"},
        )


@router.delete("/secrets/{secret_key}")
async def delete_secret(
    secret_key: str,
    namespace: str = Query(..., description="Namespace for the vault operations"),
):
    """Delete secret from user's namespace"""
    try:
        await vault_ops.delete_secret(secret_key, namespace)
        return {"status": 200, "message": {"status": "Secret deleted"}}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": 500, "message": f"Failed to delete secret: {str(e)}"},
        )


@router.post("/namespaces/create")
async def create_namespace(request: NamespaceRequest):
    """Setup namespace for new user"""
    try:
        namespace = request.namespace
        print(f"Creating namespace for user: {namespace}")
        await vault_ops.setup_user(namespace)
        logger.debug(f"Namespace created for user: {namespace}")
        return {"status": 200, "message": {"status": "Namespace created successfully"}}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": 500, "message": f"Failed to create namespace: {str(e)}"},
        )


@router.get("/namespaces/list")
async def list_namespaces(
    request: NamespaceRequest = None,
) -> List[str]:
    """List all namespaces or a specific user's namespace"""
    logger.debug("Listing namespaces")
    try:
        if request and request.namespace:
            # Check if specific namespace exists
            namespaces = await vault_ops.list_ns()
            if request.namespace in namespaces:
                return [request.namespace]
            else:
                return []
        else:
            # List all namespaces (admin only)
            namespaces = await vault_ops.list_ns()
            return namespaces
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
