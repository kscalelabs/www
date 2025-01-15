"""Defines the main entrypoint for the FastAPI app."""

import uvicorn
from fastapi import FastAPI

from www.auth import COGNITO_CLIENT_ID
from www.errors import add_exception_handlers
from www.middleware import add_middleware
from www.routers import add_routers

app = FastAPI(
    title="K-Scale",
    version="1.0.0",
    docs_url="/",
    swagger_ui_oauth2_redirect_url="/callback",
    swagger_ui_init_oauth={
        "appName": "www",
        "clientId": COGNITO_CLIENT_ID,
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": "openid email profile",
    },
)

add_middleware(app)
add_exception_handlers(app)
add_routers(app)


# For running with debugger
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=True,
        proxy_headers=True,
    )
