from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.database import engine, Base
from app.routes import auth, dealership
from app.routes import attachments as attachment_routes
from app.websocket import handle_websocket
from app.config import get_settings

# Import event handlers to register them with the event bus
# This must happen before the app starts handling requests
from app.events.handlers import notifications, websocket_broadcast  # noqa: F401
from app.events.handlers import attachment_events  # noqa: F401

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create database tables (will be replaced by Alembic migrations)
Base.metadata.create_all(bind=engine)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


async def _orphan_cleanup_loop():
    """Periodically clean up orphaned attachments (uploaded but never linked to a comment)."""
    from app.database import SessionLocal
    from app.models.models import Attachment, AttachmentStatus
    from app.storage.backend import get_storage_backend
    from datetime import datetime, timedelta

    ttl = settings.storage_orphan_ttl_minutes

    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=ttl)
            orphans = db.query(Attachment).filter(
                Attachment.comment_id.is_(None),
                Attachment.status.in_([
                    AttachmentStatus.READY,
                    AttachmentStatus.UPLOADING,
                    AttachmentStatus.QUARANTINED,
                ]),
                Attachment.created_at < cutoff,
            ).all()

            if orphans:
                storage = get_storage_backend()
                for orphan in orphans:
                    try:
                        await storage.delete(orphan.storage_key)
                        if orphan.thumbnail_storage_key:
                            await storage.delete(orphan.thumbnail_storage_key)
                    except Exception as e:
                        logger.warning(f"Failed to delete orphan storage {orphan.id}: {e}")

                    db.delete(orphan)

                db.commit()
                logger.info(f"Cleaned up {len(orphans)} orphaned attachment(s)")

        except Exception as e:
            logger.error(f"Orphan cleanup error: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start background tasks on startup, clean up on shutdown."""
    # Start orphan cleanup task
    cleanup_task = asyncio.create_task(_orphan_cleanup_loop())
    logger.info("Orphan attachment cleanup task started")

    yield

    # Cancel cleanup on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Orphan attachment cleanup task stopped")


app = FastAPI(
    title="Dealership Vehicle Evaluation API",
    version="3.0.0",
    description="Vehicle evaluation system with real-time collaboration and file attachments",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Configure CORS with specific origins from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dealership.router, prefix="/api/dealership", tags=["Dealership"])
app.include_router(attachment_routes.router, prefix="/api/attachments", tags=["Attachments"])


@app.get("/")
def read_root():
    return {
        "message": "Dealership Vehicle Evaluation API",
        "version": "3.0.0",
        "endpoints": {
            "auth": {
                "register": "/api/auth/register",
                "login": "/api/auth/login"
            },
            "vehicles": {
                "list": "/api/dealership/vehicles",
                "create": "/api/dealership/vehicles",
                "get": "/api/dealership/vehicles/{vehicle_id}",
                "update": "/api/dealership/vehicles/{vehicle_id}"
            },
            "sections": {
                "list": "/api/dealership/sections"
            },
            "comments": {
                "list": "/api/dealership/comments?vehicle_id=X&section=Y",
                "create": "/api/dealership/comments"
            },
            "notifications": {
                "list": "/api/dealership/notifications",
                "mark_read": "/api/dealership/notifications/{notification_id}/read",
                "mark_all_read": "/api/dealership/notifications/read-all"
            },
            "attachments": {
                "simple_upload": "POST /api/attachments/upload",
                "chunked_init": "POST /api/attachments/upload/init",
                "chunked_chunk": "PATCH /api/attachments/upload/{id}/chunk/{index}",
                "chunked_complete": "POST /api/attachments/upload/{id}/complete",
                "download": "GET /api/attachments/{id}/download",
                "info": "GET /api/attachments/{id}",
                "delete": "DELETE /api/attachments/{id}",
            },
            "websocket": "/ws/chat?token=X&vehicle_id=Y&section=Z"
        },
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, token: str, vehicle_id: int | None = None, section: str | None = None):
    """
    WebSocket endpoint for real-time vehicle evaluation comments.

    Parameters:
    - token: JWT authentication token
    - vehicle_id: Vehicle ID to connect to
    - section: Section name (tire, warranty, accident_damages, paint, previous_owners)
    """
    await handle_websocket(websocket, token, vehicle_id, section)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
