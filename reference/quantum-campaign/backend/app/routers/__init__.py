from app.routers.upload import router as upload_router
from app.routers.campaigns import router as campaigns_router
from app.routers.templates import router as templates_router
from app.routers.templates import modules_router
from app.routers.accounts import router as accounts_router

__all__ = [
    "upload_router",
    "campaigns_router",
    "templates_router",
    "modules_router",
    "accounts_router",
]
