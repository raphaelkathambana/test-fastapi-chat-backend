#!/usr/bin/env python3
"""
Debug script to test the FastAPI chat backend connection.
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("="*60)
print("FastAPI Chat Backend - Connection Debug Tool")
print("="*60)

# Test 1: Check if server is reachable
print("\n[Test 1] Checking server root endpoint...")
try:
    response = requests.get(f"{BASE_URL}/", timeout=5)
    print(f"✓ Status: {response.status_code}")
    print(f"✓ Response: {response.json()}")
except Exception as e:
    print(f"✗ Error: {e}")
    print("\n** Server is not running or not accessible **")
    print("Make sure server is running: python -m uvicorn app.main:app --reload")
    exit(1)

# Test 2: Check health endpoint
print("\n[Test 2] Checking health endpoint...")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"✓ Status: {response.status_code}")
    print(f"✓ Response: {response.json()}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Check docs endpoint
print("\n[Test 3] Checking API docs...")
try:
    response = requests.get(f"{BASE_URL}/docs", timeout=5)
    print(f"✓ Status: {response.status_code}")
    print(f"✓ API docs accessible at: {BASE_URL}/docs")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Try registration with valid password
print("\n[Test 4] Testing registration endpoint...")
test_data = {
    "username": "debuguser",
    "password": "DebugPass123"  # Meets requirements: 8+ chars, upper, lower, digit
}
try:
    print(f"Sending POST to: {BASE_URL}/api/auth/register")
    print(f"Data: {test_data}")
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json=test_data,
        timeout=5
    )
    print(f"✓ Status: {response.status_code}")
    print(f"✓ Headers: {dict(response.headers)}")
    print(f"✓ Response: {response.text}")

    if response.status_code == 201:
        print("\n✓✓✓ Registration endpoint works!")
    elif response.status_code == 400:
        print("\n⚠ User might already exist, try different username")
    else:
        print(f"\n✗ Unexpected status code: {response.status_code}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Try registration with invalid password (should fail validation)
print("\n[Test 5] Testing password validation...")
test_data_invalid = {
    "username": "testuser2",
    "password": "test"  # Invalid: too short, no uppercase, no digit
}
try:
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json=test_data_invalid,
        timeout=5
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 422:
        print("✓ Password validation working correctly!")
    else:
        print(f"⚠ Expected 422 validation error, got {response.status_code}")

except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60)
print("Debug complete!")
print("="*60)
