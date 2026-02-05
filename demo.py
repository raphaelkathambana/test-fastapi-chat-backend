#!/usr/bin/env python3
"""
Demo script showing FastAPI chat backend functionality without PostgreSQL.
Uses SQLite for demonstration purposes.
"""

print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                    FastAPI Chat Backend Demo                            ║
║                                                                          ║
║  This demo shows the functionality of the chat backend without          ║
║  requiring a PostgreSQL database. For testing, it uses SQLite.         ║
╚══════════════════════════════════════════════════════════════════════════╝
""")

import sys
import os

# Override database URL to use SQLite
os.environ['DATABASE_URL'] = 'sqlite:///./test_chat.db'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, User, Message
from app.utils.auth import get_password_hash, verify_password, create_access_token, decode_token
from app.utils.encryption import encrypt_message, decrypt_message
from datetime import datetime

print("\n📊 Setting up SQLite database...")
engine = create_engine("sqlite:///./test_chat.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)

print("✓ Database initialized")

print("\n" + "="*70)
print("1️⃣  USER REGISTRATION & AUTHENTICATION")
print("="*70)

db = Session()

# Create users
users_data = [
    ("alice", "password123"),
    ("bob", "secret456"),
]

created_users = []
for username, password in users_data:
    # Check if user exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"   User '{username}' already exists")
        created_users.append(existing)
    else:
        user = User(
            username=username,
            hashed_password=get_password_hash(password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created_users.append(user)
        print(f"✓  User registered: {username}")

print(f"\n   Total users: {len(created_users)}")

print("\n" + "="*70)
print("2️⃣  PASSWORD VERIFICATION")
print("="*70)

alice = created_users[0]
print(f"   Testing password for user: {alice.username}")
print(f"   ✓ Correct password: {verify_password('password123', alice.hashed_password)}")
print(f"   ✗ Wrong password: {verify_password('wrongpass', alice.hashed_password)}")

print("\n" + "="*70)
print("3️⃣  JWT TOKEN GENERATION")
print("="*70)

token = create_access_token(data={"sub": alice.username})
print(f"   Generated token for '{alice.username}':")
print(f"   {token[:50]}...")

token_data = decode_token(token)
print(f"\n   Decoded token username: {token_data.username}")

print("\n" + "="*70)
print("4️⃣  MESSAGE ENCRYPTION & STORAGE")
print("="*70)

messages_text = [
    ("alice", "Hey everyone! How's it going?"),
    ("bob", "Hi Alice! Great to be here 👋"),
    ("alice", "I'm excited to test this encrypted chat!"),
    ("bob", "The encryption keeps our messages safe 🔒"),
    ("alice", "Absolutely! Privacy is important."),
]

print("   Encrypting and storing messages...")
for username, text in messages_text:
    user = db.query(User).filter(User.username == username).first()
    encrypted_content = encrypt_message(text)
    
    message = Message(
        user_id=user.id,
        content=encrypted_content
    )
    db.add(message)
    print(f"   ✓ [{username}] Message encrypted and stored")

db.commit()

print("\n" + "="*70)
print("5️⃣  MESSAGE RETRIEVAL & DECRYPTION")
print("="*70)

messages = db.query(Message).order_by(Message.created_at).all()
print(f"\n   Retrieved {len(messages)} messages from database:\n")

for msg in messages:
    decrypted = decrypt_message(msg.content)
    timestamp = msg.created_at.strftime("%H:%M:%S")
    print(f"   [{timestamp}] {msg.user.username}: {decrypted}")

print("\n" + "="*70)
print("6️⃣  DATABASE STATISTICS")
print("="*70)

user_count = db.query(User).count()
message_count = db.query(Message).count()

print(f"   Total users: {user_count}")
print(f"   Total messages: {message_count}")
print(f"   Messages per user:")

for user in created_users:
    user_messages = db.query(Message).filter(Message.user_id == user.id).count()
    print(f"      - {user.username}: {user_messages} messages")

print("\n" + "="*70)
print("7️⃣  ENCRYPTION VERIFICATION")
print("="*70)

sample_message = messages[0]
print(f"\n   Original encrypted content (first 80 chars):")
print(f"   {sample_message.content[:80]}...")

decrypted_content = decrypt_message(sample_message.content)
print(f"\n   Decrypted content:")
print(f"   {decrypted_content}")

# Verify re-encryption works
re_encrypted = encrypt_message(decrypted_content)
re_decrypted = decrypt_message(re_encrypted)
assert re_decrypted == decrypted_content
print(f"\n   ✓ Re-encryption/decryption verified")

db.close()

print("\n" + "="*70)
print("✅ DEMO COMPLETED SUCCESSFULLY!")
print("="*70)

print("""
📝 Summary:
   • User authentication with password hashing ✓
   • JWT token generation and validation ✓
   • Message encryption using Fernet (AES-128) ✓
   • Secure database storage ✓
   • Message retrieval and decryption ✓

🚀 To run the full application with PostgreSQL:
   1. Setup PostgreSQL database
   2. Update .env file with database credentials
   3. Run: python -m uvicorn app.main:app --reload
   4. Run client: python client.py

📚 View API docs at: http://localhost:8000/docs
""")

# Clean up
if os.path.exists("test_chat.db"):
    print("🧹 Cleaning up demo database...")
    os.remove("test_chat.db")
    print("   ✓ Demo database removed")
