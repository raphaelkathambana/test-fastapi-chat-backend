from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.database import engine, Base
from app.routes import auth, chat, dealership
from app.websocket import handle_websocket
from app.config import get_settings

# Import event handlers to register them with the event bus
# This must happen before the app starts handling requests
from app.events.handlers import notifications, websocket_broadcast  # noqa: F401

# Get settings
settings = get_settings()

# Create database tables (will be replaced by Alembic migrations)
Base.metadata.create_all(bind=engine)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Dealership Vehicle Evaluation API",
    version="2.0.0",
    description="Vehicle evaluation system with real-time collaboration"
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(dealership.router, prefix="/api/dealership", tags=["Dealership"])


@app.get("/")
def read_root():
    return {
        "message": "Dealership Vehicle Evaluation API",
        "version": "2.0.0",
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
            "websocket": "/ws/chat?token=X&vehicle_id=Y&section=Z"
        },
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, token: str, vehicle_id: int = None, section: str = None):
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
