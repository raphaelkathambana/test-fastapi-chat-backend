#!/usr/bin/env python3
"""
Comprehensive test suite for FastAPI Chat Backend.
Run with: python test_app.py
"""
from app.utils.encryption import encrypt_message, decrypt_message
from app.utils.auth import get_password_hash, verify_password

def test_encryption():
    """Test encryption and decryption utilities."""
    print("\n🔐 Testing Encryption")
    print("-" * 70)
    
    message = "Hello, World! 🌍"
    encrypted = encrypt_message(message)
    decrypted = decrypt_message(encrypted)
    
    assert decrypted == message, "Decryption failed"
    print(f"✓ Original: {message}")
    print(f"✓ Encrypted: {encrypted[:50]}...")
    print(f"✓ Decrypted: {decrypted}")
    print("✓ Encryption test PASSED")

def test_password_hashing():
    """Test password hashing and verification."""
    print("\n🔑 Testing Password Hashing")
    print("-" * 70)
    
    password = "mySecurePassword123"
    hashed = get_password_hash(password)
    
    assert verify_password(password, hashed), "Password verification failed"
    assert not verify_password("wrongPassword", hashed), "Should reject wrong password"
    
    print(f"✓ Password hashed correctly")
    print(f"✓ Verification works")
    print("✓ Password hashing test PASSED")

def test_database_models():
    """Test database models with SQLite."""
    print("\n💾 Testing Database Models")
    print("-" * 70)
    
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.models import Base, User, Message
    
    # Create in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Create test user
    user = User(
        username="testuser",
        hashed_password=get_password_hash("testpass")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    assert user.id is not None
    print(f"✓ User created: {user.username}")
    
    # Create test message
    encrypted_content = encrypt_message("Test message")
    message = Message(
        user_id=user.id,
        content=encrypted_content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    assert message.id is not None
    print(f"✓ Message created and encrypted")
    
    # Retrieve and decrypt
    retrieved = db.query(Message).first()
    decrypted = decrypt_message(retrieved.content)
    assert decrypted == "Test message"
    print(f"✓ Message retrieved and decrypted: {decrypted}")
    
    db.close()
    print("✓ Database model tests PASSED")

def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print(" FastAPI Chat Backend - Test Suite".center(70))
    print("=" * 70)
    
    try:
        test_encryption()
        test_password_hashing()
        test_database_models()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!".center(70))
        print("=" * 70)
        print()
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
