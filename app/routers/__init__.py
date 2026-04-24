from .admin import router as admin_router
from .seller import router as seller_router
from .user import router as user_router

__all__ = ["admin_router", "seller_router", "user_router"]
