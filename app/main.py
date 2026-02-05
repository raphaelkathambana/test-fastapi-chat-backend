from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import auth, chat
from app.websocket import handle_websocket

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI Chat Backend", version="1.0.0")

# Configure CORS
# WARNING: In production, replace allow_origins=["*"] with specific origins
# Example: allow_origins=["https://yourdomain.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/")
def read_root():
    return {
        "message": "FastAPI Chat Backend",
        "version": "1.0.0",
        "endpoints": {
            "register": "/api/auth/register",
            "login": "/api/auth/login",
            "messages": "/api/chat/messages",
            "websocket": "/ws/chat"
        }
    }


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await handle_websocket(websocket, token)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
