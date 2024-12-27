"""Defines the authentication endpoints for the API."""

from fastapi import APIRouter

from www.app.routers.auth.api import router as api_router
from www.app.routers.auth.github import router as github_router
from www.app.routers.auth.google import router as google_router
from www.app.routers.auth.test import router as test_router
from www.settings import settings

router = APIRouter()

router.include_router(api_router, prefix="/api")
router.include_router(github_router, prefix="/github")
router.include_router(google_router, prefix="/google")

if settings.site.enable_test_endpoint:
    router.include_router(test_router, prefix="/test")
