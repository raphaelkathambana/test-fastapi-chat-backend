# FastAPI Chat Backend

A secure, production-ready real-time chat application built with FastAPI featuring end-to-end encryption, PostgreSQL database persistence, and WebSocket communication.

## Features

- 🔐 **End-to-End Encryption**: All messages are encrypted before storage using Fernet (AES-128-CBC with HMAC authentication)
- 💬 **Real-time Chat**: WebSocket-based communication for instant messaging
- 🔒 **Secure Authentication**: JWT-based authentication with bcrypt password hashing
- 💾 **Database Persistence**: PostgreSQL with Alembic migrations
- 🛡️ **Security Hardened**:
  - Rate limiting on authentication endpoints
  - Password complexity validation
  - Username format validation
  - Configurable CORS origins
  - Header-based authentication (not query params)
  - No hardcoded secrets (required .env configuration)
- 🖥️ **TUI Client**: Terminal User Interface for easy testing
- 🚀 **Modern Stack**: Built with FastAPI, SQLAlchemy 2.0, and asyncio

## Project Structure

```
.
├── app/
│   ├── config.py          # Configuration with separate DB credentials
│   ├── database.py        # Database connection and session
│   ├── main.py           # FastAPI application with rate limiting
│   ├── websocket.py      # WebSocket connection manager
│   ├── models/
│   │   ├── models.py     # SQLAlchemy database models
│   │   └── schemas.py    # Pydantic schemas with validation
│   ├── routes/
│   │   ├── auth.py       # Authentication endpoints (rate limited)
│   │   └── chat.py       # Chat endpoints (header-based auth)
│   └── utils/
│       ├── auth.py       # Authentication utilities
│       └── encryption.py # Encryption/decryption utilities
├── alembic/              # Database migrations
├── client.py             # TUI chat client
├── docker-compose.yml    # PostgreSQL container configuration
├── requirements.txt      # All Python dependencies
└── .env.example         # Environment variables template
```

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database (via Docker or local installation)
- OpenSSL (for generating secret keys)

## Installation

### 1. Clone and Setup Virtual Environment

```bash
git clone <repository-url>
cd test-fastapi-chat-backend

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

**IMPORTANT:** This application requires a `.env` file to run. No defaults are provided for security reasons.

```bash
cp .env.example .env
```

Edit `.env` and set the following **required** variables:

```bash
# Generate SECRET_KEY (for JWT signing)
openssl rand -hex 32

# Generate ENCRYPTION_KEY (for message encryption)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Update your `.env` file:
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=chatdb
DATABASE_USER=postgres
DATABASE_PASSWORD=your-secure-password

SECRET_KEY=<output-from-openssl-command>
ENCRYPTION_KEY=<output-from-python-command>

# Optional: Customize CORS origins
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### 4. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

Wait for PostgreSQL to be ready (check with `docker-compose ps`).

### 5. Run Database Migrations

```bash
alembic upgrade head
```

This will create the `users` and `messages` tables.

## Usage

### Starting the Server

```bash
python -m uvicorn app.main:app --reload
```

The server will start at `http://localhost:8000`

- API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

### Using the TUI Client

In a separate terminal (with venv activated):

```bash
python client.py
```

Follow the prompts to:
1. Register a new user or login
2. View message history
3. Start chatting in real-time

**Note:** Password requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

**Client Commands**:
- `/quit`, `/exit`, `/q` - Exit the chat
- `/help` - Show available commands

### Testing with Multiple Clients

1. Open multiple terminal windows
2. Run `python client.py` in each terminal
3. Register/login with different usernames
4. Send messages and see them appear in all connected clients

## API Endpoints

### Authentication

**Register a new user:**
```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "john",
  "password": "SecurePass123"
}
```

Rate limit: 5 requests per minute per IP

**Login and get access token:**
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "john",
  "password": "SecurePass123"
}
```

Rate limit: 10 requests per minute per IP

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Chat

**Get message history:**
```bash
GET /api/chat/messages?limit=50
Authorization: Bearer <access_token>
```

**WebSocket chat:**
```
WS /ws/chat?token=<access_token>
```

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

### Authentication & Authorization
- JWT tokens with 30-minute expiration
- bcrypt password hashing (12 rounds)
- Bearer token authentication (Authorization header)

### Input Validation
- **Username**: 3-50 characters, alphanumeric + underscore/hyphen only
- **Password**: 8-128 characters, must contain uppercase, lowercase, and digit

### Rate Limiting
- Registration: 5 attempts per minute per IP
- Login: 10 attempts per minute per IP

### Data Protection
- All messages encrypted at rest (Fernet/AES-128)
- No passwords stored in plain text
- Separate database credentials (not in connection string)

### Network Security
- Configurable CORS origins (no wildcard in production)
- HTTPS recommended for production
- Health check endpoint for monitoring

## Database Migrations

This project uses Alembic for database migrations.

**Create a new migration:**
```bash
alembic revision --autogenerate -m "Description of changes"
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Rollback last migration:**
```bash
alembic downgrade -1
```

**View migration history:**
```bash
alembic history
```

## Docker Usage

The included `docker-compose.yml` provides a PostgreSQL container for development.

**Start:**
```bash
docker-compose up -d
```

**Stop:**
```bash
docker-compose down
```

**Stop and remove data:**
```bash
docker-compose down -v
```

**View logs:**
```bash
docker-compose logs -f postgres
```

## Development

### Running Tests

```bash
python test_app.py
```

### Code Structure

- **app/config.py**: Centralized configuration with Pydantic Settings
- **app/database.py**: SQLAlchemy engine and session management
- **app/models/**: Database models and Pydantic schemas
- **app/routes/**: API endpoint handlers
- **app/utils/**: Authentication and encryption utilities
- **alembic/**: Database migration scripts

## Production Deployment

### Required Steps

1. **Set strong secrets in .env**:
   ```bash
   SECRET_KEY=$(openssl rand -hex 32)
   ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   ```

2. **Configure CORS for your domain**:
   ```env
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

3. **Use a managed PostgreSQL database**:
   ```env
   DATABASE_HOST=your-db-host.example.com
   DATABASE_USER=your_db_user
   DATABASE_PASSWORD=strong-password
   DATABASE_NAME=chatdb_prod
   ```

4. **Run with production ASGI server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

5. **Setup HTTPS**: Use nginx or similar as a reverse proxy with SSL certificates

6. **Apply database migrations**:
   ```bash
   alembic upgrade head
   ```

### Recommended Enhancements for Production

- Add logging (structured logging with correlation IDs)
- Implement monitoring (Prometheus metrics)
- Add health checks for database connectivity
- Implement email verification for new users
- Add password reset functionality
- Implement session management with refresh tokens
- Add WebSocket heartbeat/ping-pong
- Implement message pagination
- Add user presence indicators
- Set up automated backups for PostgreSQL

## Troubleshooting

**Error: "Failed to load configuration!"**
- Make sure you created `.env` file from `.env.example`
- Verify all required variables are set

**Error: "Connection refused" to PostgreSQL**
- Start Docker: `docker-compose up -d`
- Check status: `docker-compose ps`
- View logs: `docker-compose logs postgres`

**Error: "Invalid token" when connecting**
- Token may have expired (30 minutes)
- Login again to get a new token

**Rate limit exceeded**
- Wait 60 seconds
- This is a security feature to prevent brute force attacks

## Contributing

Contributions are welcome! Please ensure:
1. All tests pass
2. Code follows existing style
3. Security best practices are maintained
4. Documentation is updated

## License

MIT License

## Security Notes

- Never commit `.env` file to version control
- Use strong, randomly generated keys in production
- Enable HTTPS for production deployments
- Regularly update dependencies
- Monitor rate limit violations
- Implement additional security layers as needed
