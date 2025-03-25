import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from core.server.routes.web import router as web_router
from core.server.routes.vault import router as vault_router
from core.server.constants import (
    APP_NAME,
    APP_VERSION,
    IS_DEBUG,
    HOST,
    PORT,
    WORKERS,
    GLOBAL_PREFIX,
)
from fastapi.responses import JSONResponse
from core.utils.logger import Logger
import time
from core.server.utils.vault_operations import vault_ops
from contextlib import asynccontextmanager

logger = Logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create default namespace from environment variable
    namespace = os.environ.get("VITE_APP_VA_NAMESPACE")
    if namespace:
        try:
            # Check if namespace already exists
            existing_namespaces = await vault_ops.list_ns()
            if f"{namespace}/" in existing_namespaces:
                logger.info(f"Namespace {namespace} already exists, skipping creation")
            else:
                logger.info(f"Creating default namespace: {namespace}")
                await vault_ops.setup_user(namespace)
                logger.info(f"Default namespace created successfully: {namespace}")
        except Exception as e:
            logger.error(f"Failed to create default namespace: {str(e)}")
    yield


def get_app() -> FastAPI:
    """Initialize and configure FastAPI application"""
    start_time = time.time()

    fast_app = FastAPI(
        title=APP_NAME,
        description="""
        ## Web Agent API Documentation
        
        This API provides endpoints for web automation and browser control.
        
        ### Features
        - Web automation and browser control
        - Real-time status updates
        """,
        version=APP_VERSION,
        debug=IS_DEBUG,
        openapi_tags=[
            {"name": "Web Automation", "description": "Web automation operations"}
        ],
        lifespan=lifespan,
    )

    # Setup CORS middleware
    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Allow all origins for simplicity
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include only the web router
    fast_app.include_router(web_router, prefix=GLOBAL_PREFIX)
    fast_app.include_router(vault_router, prefix=GLOBAL_PREFIX)

    print(
        f"DEBUG: Total app initialization took {time.time() - start_time:.2f} seconds"
    )

    return fast_app


app = get_app()


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"ERROR: Generic exception encountered: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Unexpected error occurred"},
    )


if __name__ == "__main__":
    print(f"DEBUG: Starting {APP_NAME} v{APP_VERSION}")
    print(f"DEBUG: Debug mode: {IS_DEBUG}")
    uvicorn.run(
        "core.server.main:app",
        host=HOST,
        port=PORT,
        workers=WORKERS,
        reload=IS_DEBUG,
        log_level="info",
    )
