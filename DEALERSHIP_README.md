# Dealership Vehicle Evaluation System

A real-time vehicle evaluation system for dealerships, built on FastAPI with WebSocket support for collaborative commenting.

## Overview

This system allows multiple employees to collaborate on vehicle evaluations by adding comments to specific sections of the evaluation process. Features include:

- **Vehicle Management**: Track vehicles through the evaluation pipeline
- **Section-based Comments**: Comments organized by evaluation sections
- **Real-time Collaboration**: WebSocket-based live updates when employees comment
- **@Mentions**: Tag other employees to notify them about specific comments
- **Notifications**: Get notified when mentioned in comments

## Architecture

### Data Models

#### Vehicle
- **Fields**: VIN, make, model, year, status
- **Status Flow**: Pending → Online Evaluation → Inspection → Completed/Rejected

#### Evaluation Sections (5 sections)

**Online Evaluation (Sections 1-3):**
1. Tire Evaluation
2. Warranty
3. Accident & Damages

**Inspection (Sections 4-5):**
4. Paint Inspection
5. Previous Owners

#### Comment
- Tied to a specific vehicle and section
- Contains encrypted content
- Tracks author and timestamp
- Supports @mentions

#### Notification
- Created when an employee is @mentioned
- Links to the specific comment
- Tracks read/unread status

### API Endpoints

#### Authentication
```
POST   /api/auth/register     - Register new employee
POST   /api/auth/login        - Login and get JWT token
```

#### Vehicles
```
GET    /api/dealership/vehicles              - List all vehicles
POST   /api/dealership/vehicles              - Create new vehicle
GET    /api/dealership/vehicles/{id}         - Get vehicle details
PATCH  /api/dealership/vehicles/{id}         - Update vehicle
```

#### Sections
```
GET    /api/dealership/sections              - List all sections with metadata
```

#### Comments
```
GET    /api/dealership/comments              - Get comments (by vehicle_id + section)
POST   /api/dealership/comments              - Create new comment
```

#### Notifications
```
GET    /api/dealership/notifications         - Get notifications
PATCH  /api/dealership/notifications/{id}/read - Mark as read
PATCH  /api/dealership/notifications/read-all  - Mark all as read
```

#### WebSocket
```
WS     /ws/chat?token={jwt}&vehicle_id={id}&section={name}
```

### WebSocket Protocol

**Connect**: Requires JWT token, vehicle_id, and section name
```
ws://localhost:8000/ws/chat?token=<JWT>&vehicle_id=1&section=tire
```

**Send Comment**:
```json
{
  "type": "comment",
  "content": "Tires need replacement @john"
}
```

**Receive Comment**:
```json
{
  "type": "comment",
  "comment_id": 123,
  "username": "alice",
  "content": "Tires need replacement @john",
  "vehicle_id": 1,
  "section": "tire",
  "timestamp": "2026-02-05T14:30:00",
  "mentions": ["john"]
}
```

**Receive Mention Notification**:
```json
{
  "type": "mention",
  "message": "You were mentioned by alice in Toyota Camry - tire",
  "comment_id": 123,
  "vehicle_id": 1,
  "section": "tire"
}
```

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- PostgreSQL (via Docker or local)
- All dependencies from `requirements.txt`

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Generate secure keys:
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Update `.env`:
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=chatdb
DATABASE_USER=postgres
DATABASE_PASSWORD=your-secure-password

SECRET_KEY=<generated-secret-key>
ENCRYPTION_KEY=<generated-encryption-key>

CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### 3. Start Database

Using Docker:
```bash
docker-compose up -d
```

Wait for PostgreSQL to be ready:
```bash
docker-compose ps
```

### 4. Run Migrations and Seed Data

Run the setup script:
```bash
python setup_db.py
```

This will:
1. Create all database tables (users, vehicles, comments, notifications)
2. Seed 5 test vehicles

Or run manually:
```bash
# Run migrations
python -c "from alembic import command; from alembic.config import Config; command.upgrade(Config('alembic.ini'), 'head')"

# Seed vehicles
python seed_vehicles.py
```

### 5. Start the Server

```bash
python -m uvicorn app.main:app --reload
```

Server will start at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Using the TUI Client

### Start the Client

```bash
python dealership_client.py
```

### Workflow

1. **Login/Register**: Choose option 1 (Login) or 2 (Register)

2. **Main Menu**:
   - View Vehicles: See all vehicles in the system
   - View Notifications: Check @mentions
   - Logout: Exit the system

3. **Select Vehicle**: Choose a vehicle from the list

4. **Select Section**: Choose an evaluation section (1-5)

5. **Comment**:
   - View existing comments
   - Type new comments
   - Use `@username` to mention other employees
   - Commands:
     - `/q`, `/quit`, `/exit` - Return to main menu
     - `/back` - Change section
     - `/help` - Show help

### Example Session

```
1. Login with username: alice, password: SecurePass123
2. Select "1. View Vehicles"
3. Select vehicle: "1. 2020 Toyota Camry"
4. Select section: "1. Tire Evaluation"
5. Type: "Front tires worn 60%, recommend replacement @bob"
6. Bob will receive a notification
```

## Testing with Multiple Clients

1. Open 3 terminal windows
2. Run `python dealership_client.py` in each
3. Register/login with different users: alice, bob, charlie
4. Have all users select the same vehicle and section
5. Comments will appear in real-time across all clients
6. Use @mentions to notify specific users

## Test Data

The seed script creates 5 vehicles:

1. **2020 Toyota Camry** (VIN: 1HGBH41JXMN109186) - Online Evaluation
2. **2019 Honda Accord** (VIN: 2HGFG12678H542398) - Inspection
3. **2021 Ford Mustang** (VIN: 3FADP4EJ2FM123456) - Online Evaluation
4. **2022 Tesla Model S** (VIN: 5YJSA1E14HF123789) - Pending
5. **2018 Chevrolet Corvette** (VIN: 1G1YY22G965123456) - Completed

## Security Features

All security features from v2.0 are maintained:
- JWT authentication
- bcrypt password hashing
- End-to-end message encryption
- Rate limiting on auth endpoints
- Password complexity requirements
- Username validation
- Configurable CORS

See [SECURITY.md](SECURITY.md) for full details.

## Database Schema

```
users
  ├─ id (PK)
  ├─ username (unique)
  ├─ hashed_password
  └─ created_at

vehicles
  ├─ id (PK)
  ├─ vin (unique)
  ├─ make
  ├─ model
  ├─ year
  ├─ status (enum)
  ├─ created_at
  └─ updated_at

comments
  ├─ id (PK)
  ├─ vehicle_id (FK → vehicles)
  ├─ section (enum)
  ├─ user_id (FK → users)
  ├─ content (encrypted)
  └─ created_at

notifications
  ├─ id (PK)
  ├─ recipient_id (FK → users)
  ├─ comment_id (FK → comments)
  ├─ is_read
  └─ created_at
```

## Troubleshooting

**Connection refused to server**:
- Ensure server is running: `python -m uvicorn app.main:app --reload`
- Check server logs for errors

**Database connection errors**:
- Verify PostgreSQL is running: `docker-compose ps`
- Check .env database credentials
- Ensure migrations have run: `python setup_db.py`

**Token expired errors**:
- JWT tokens expire after 30 minutes
- Re-login to get a new token

**WebSocket connection fails**:
- Verify vehicle_id exists
- Verify section name is valid (tire, warranty, accident_damages, paint, previous_owners)
- Check token is valid

**@Mentions not working**:
- Ensure username exists in the system
- Check notification endpoint: `GET /api/dealership/notifications`
- Mentioned user must be registered

## Development

### Adding New Sections

To add new evaluation sections:

1. Update `SectionType` enum in `app/models/models.py`
2. Create migration: `alembic revision -m "add_new_section"`
3. Update section list in `app/routes/dealership.py` → `list_sections()`
4. Update `get_section_display_name()` in `dealership_client.py`

### Running Tests

```bash
python test_app.py
```

## License

MIT License

## Support

For issues and feature requests, please create an issue in the repository.
