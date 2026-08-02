"""API v1 router configuration.

This module sets up the main API router and includes all sub-routers for different
endpoints like authentication and chatbot functionality.
"""

from app.prefs.api import router as notification_preferences_router
from fastapi import APIRouter

from app.api.dashboards import router as dashboards_router
from app.api.v1.atrisk import router as atrisk_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.progress import router as progress_router
from app.api.v1.tickets import router as tickets_router
from app.core.logging import logger
from app.kb.admin_api import router as kb_admin_router

api_router = APIRouter()

# Include routers
api_router.include_router(kb_admin_router, prefix="/kb", tags=["KB Admin"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])
api_router.include_router(tickets_router, prefix="/tickets", tags=["Ops Tickets"])
api_router.include_router(dashboards_router, prefix="/dashboards", tags=["Dashboards"])
api_router.include_router(atrisk_router, prefix="/atrisk", tags=["At-Risk"])
api_router.include_router(progress_router, prefix="/progress", tags=["Progress Ingestion"])
api_router.include_router(notification_preferences_router, prefix="/notifications", tags=["Notification Preferences"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status information.
    """
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
