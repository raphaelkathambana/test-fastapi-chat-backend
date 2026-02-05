#!/usr/bin/env python3
"""
Test configuration loading
"""
import sys
import os

print("="*60)
print("Configuration Test")
print("="*60)

# Test 1: Check if .env exists
print("\n[Test 1] Checking .env file...")
if os.path.exists('.env'):
    print("✓ .env file exists")
    print("\nContents:")
    with open('.env', 'r') as f:
        for i, line in enumerate(f, 1):
            # Show line but hide sensitive values
            if '=' in line:
                key, value = line.split('=', 1)
                if 'PASSWORD' in key or 'KEY' in key:
                    print(f"  {i}: {key}=***hidden***")
                else:
                    print(f"  {i}: {line.strip()}")
            else:
                print(f"  {i}: {line.strip()}")
else:
    print("✗ .env file NOT found!")
    print("Create it with: cp .env.example .env")
    sys.exit(1)

# Test 2: Try loading settings
print("\n[Test 2] Loading settings...")
try:
    from app.config import get_settings
    settings = get_settings()
    print("✓ Settings loaded successfully!")
    print(f"  DATABASE_HOST: {settings.database_host}")
    print(f"  DATABASE_PORT: {settings.database_port}")
    print(f"  DATABASE_NAME: {settings.database_name}")
    print(f"  DATABASE_USER: {settings.database_user}")
    print(f"  DATABASE_PASSWORD: ***hidden***")
    print(f"  SECRET_KEY: {settings.secret_key[:20]}...")
    print(f"  ENCRYPTION_KEY: {settings.encryption_key[:20]}...")
    print(f"  CORS_ORIGINS: {settings.cors_origins}")
    print(f"  DATABASE_URL: {settings.database_url[:50]}...")
except Exception as e:
    print(f"✗ Failed to load settings!")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Try importing app
print("\n[Test 3] Importing FastAPI app...")
try:
    from app.main import app
    print("✓ App imported successfully!")
    print(f"  App title: {app.title}")
    print(f"  Number of routes: {len(app.routes)}")
    print("\n  Routes:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(route.methods) if route.methods else 'WS'
            print(f"    {methods:10} {route.path}")
except Exception as e:
    print(f"✗ Failed to import app!")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check if routes are registered
print("\n[Test 4] Checking route registration...")
expected_routes = [
    "/",
    "/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/chat/messages",
    "/ws/chat",
]

registered_paths = [route.path for route in app.routes if hasattr(route, 'path')]
for expected in expected_routes:
    if expected in registered_paths:
        print(f"  ✓ {expected}")
    else:
        print(f"  ✗ {expected} - MISSING!")

print("\n" + "="*60)
print("Configuration test complete!")
print("="*60)
