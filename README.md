# FastAPI Chat Backend

A real-time chat application built with FastAPI featuring end-to-end encryption, PostgreSQL database persistence, and WebSocket communication.

## Features

- 🔐 **End-to-End Encryption**: All messages are encrypted before storage using Fernet (AES-128-CBC with HMAC authentication)
- 💬 **Real-time Chat**: WebSocket-based communication for instant messaging
- 🔒 **Authentication**: JWT-based user authentication and authorization
- 💾 **Database Persistence**: Messages stored in PostgreSQL database
- 🖥️ **TUI Client**: Terminal User Interface for easy testing
- 🚀 **Modern Stack**: Built with FastAPI (latest version), SQLAlchemy, and asyncio

## Project Structure

```
.
├── app/
│   ├── config.py          # Configuration and settings
│   ├── database.py        # Database connection and session
│   ├── main.py           # FastAPI application entry point
│   ├── websocket.py      # WebSocket connection manager
│   ├── models/
│   │   ├── models.py     # SQLAlchemy database models
│   │   └── schemas.py    # Pydantic schemas
│   ├── routes/
│   │   ├── auth.py       # Authentication endpoints
│   │   └── chat.py       # Chat endpoints
│   └── utils/
│       ├── auth.py       # Authentication utilities
│       └── encryption.py # Encryption/decryption utilities
├── client.py             # TUI chat client for testing
├── requirements.txt      # Python dependencies
└── .env.example         # Environment variables template
```

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd test-fastapi-chat-backend
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup PostgreSQL database**:
   ```bash
   # Create a database named 'chatdb'
   createdb chatdb
   
   # Or using psql
   psql -U postgres
   CREATE DATABASE chatdb;
   \q
   ```

5. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and secret keys
   ```

   Example `.env`:
   ```
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/chatdb
   SECRET_KEY=your-secret-key-change-this-in-production
   ENCRYPTION_KEY=your-encryption-key-change-this-in-production
   ```

## Usage

### Starting the Server

Run the FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

The server will start at `http://localhost:8000`

Visit `http://localhost:8000` to see the API information.

### Using the TUI Client

In a separate terminal, run the chat client:

```bash
python client.py
```

Follow the prompts to:
1. Register a new user or login
2. View message history
3. Start chatting in real-time

**Client Commands**:
- `/quit`, `/exit`, `/q` - Exit the chat
- `/help` - Show available commands

### Testing with Multiple Clients

To test the chat functionality:

1. Open multiple terminal windows
2. Run `python client.py` in each terminal
3. Register/login with different usernames
4. Send messages and see them appear in all connected clients

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register a new user
  ```json
  {
    "username": "john",
    "password": "secret123"
  }
  ```

- `POST /api/auth/login` - Login and get access token
  ```json
  {
    "username": "john",
    "password": "secret123"
  }
  ```

### Chat

- `GET /api/chat/messages?token=<access_token>&limit=50` - Get message history

### WebSocket

- `WS /ws/chat?token=<access_token>` - WebSocket endpoint for real-time chat

  Send messages:
  ```json
  {
    "type": "message",
    "content": "Hello, world!"
  }
  ```

  Receive messages:
  ```json
  {
    "type": "message",
    "username": "john",
    "content": "Hello, world!",
    "timestamp": "2024-01-01T12:00:00"
  }
  ```

## Security Features

1. **Password Hashing**: User passwords are hashed using bcrypt
2. **JWT Authentication**: Secure token-based authentication
3. **Message Encryption**: All messages encrypted with Fernet (AES-128-CBC with HMAC authentication)
4. **CORS Configuration**: Configurable CORS middleware (restrict origins in production)

## Development

### API Documentation

FastAPI provides interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Database Schema

**Users Table**:
- id (Primary Key)
- username (Unique)
- hashed_password
- created_at

**Messages Table**:
- id (Primary Key)
- user_id (Foreign Key)
- content (Encrypted)
- created_at

## Production Deployment

For production deployment:

1. **Update environment variables**:
   - Use strong, random SECRET_KEY and ENCRYPTION_KEY
   - Configure proper DATABASE_URL
   - Set CORS allowed origins

2. **Use a production ASGI server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Setup HTTPS**: Use a reverse proxy (nginx) with SSL certificates

4. **Database migrations**: Consider using Alembic for database migrations

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
