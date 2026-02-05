#!/usr/bin/env python3
"""
TUI Chat Client for testing the FastAPI chat backend.
"""
import asyncio
import websockets
import json
import sys
import os
from datetime import datetime
from typing import Optional
import requests


class ChatClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
        self.token: Optional[str] = None
        self.username: Optional[str] = None
        self.websocket = None
        self.running = False
    
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self):
        print("=" * 60)
        print(" FastAPI Chat Client".center(60))
        print("=" * 60)
        if self.username:
            print(f" Logged in as: {self.username}".center(60))
            print("=" * 60)
    
    def register(self, username: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/register",
                json={"username": username, "password": password}
            )
            if response.status_code == 201:
                print(f"✓ User '{username}' registered successfully!")
                return True
            else:
                print(f"✗ Registration failed: {response.json().get('detail', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def login(self, username: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.username = username
                print(f"✓ Logged in as '{username}'")
                return True
            else:
                print(f"✗ Login failed: {response.json().get('detail', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    def get_message_history(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/chat/messages",
                params={"token": self.token, "limit": 20}
            )
            if response.status_code == 200:
                messages = response.json()
                self.clear_screen()
                self.print_header()
                print("\n--- Message History ---")
                for msg in messages:
                    timestamp = msg["created_at"].split("T")[1].split(".")[0]
                    print(f"[{timestamp}] {msg['username']}: {msg['content']}")
                print("-" * 60)
            else:
                print("✗ Failed to fetch message history")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    async def receive_messages(self):
        """Receive and display messages from WebSocket."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "system":
                    print(f"\n[SYSTEM] {data['message']}")
                elif data["type"] == "message":
                    timestamp = datetime.fromisoformat(data["timestamp"]).strftime("%H:%M:%S")
                    print(f"\n[{timestamp}] {data['username']}: {data['content']}")
                print("> ", end="", flush=True)
        except websockets.exceptions.ConnectionClosed:
            print("\n[SYSTEM] Connection closed")
            self.running = False
        except Exception as e:
            print(f"\n[ERROR] {e}")
            self.running = False
    
    async def send_messages(self):
        """Send messages to WebSocket."""
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                # Read input asynchronously
                message = await loop.run_in_executor(None, sys.stdin.readline)
                message = message.strip()
                
                if message:
                    if message.lower() in ['/quit', '/exit', '/q']:
                        self.running = False
                        break
                    elif message == '/help':
                        print("\nCommands:")
                        print("  /quit, /exit, /q - Exit chat")
                        print("  /help - Show this help")
                        print("> ", end="", flush=True)
                    else:
                        await self.websocket.send(json.dumps({
                            "type": "message",
                            "content": message
                        }))
            except Exception as e:
                print(f"\n[ERROR] {e}")
                self.running = False
                break
    
    async def start_chat(self):
        """Start the WebSocket chat."""
        try:
            uri = f"{self.ws_url}/ws/chat?token={self.token}"
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                self.running = True
                
                print("\nConnected to chat! Type your messages and press Enter.")
                print("Commands: /quit, /exit, /q to exit | /help for help\n")
                print("> ", end="", flush=True)
                
                # Run receive and send tasks concurrently
                receive_task = asyncio.create_task(self.receive_messages())
                send_task = asyncio.create_task(self.send_messages())
                
                # Wait for either task to complete
                await asyncio.gather(receive_task, send_task, return_exceptions=True)
        except Exception as e:
            print(f"\n✗ Connection error: {e}")
    
    def run(self):
        """Main entry point."""
        self.clear_screen()
        self.print_header()
        
        print("\n1. Login")
        print("2. Register")
        print("3. Exit")
        
        choice = input("\nChoose an option: ").strip()
        
        if choice == "3":
            print("Goodbye!")
            return
        
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        if choice == "2":
            if not self.register(username, password):
                input("\nPress Enter to exit...")
                return
            # Auto-login after registration
            input("\nPress Enter to login...")
        
        if not self.login(username, password):
            input("\nPress Enter to exit...")
            return
        
        # Show message history
        input("\nPress Enter to view chat history and connect...")
        self.get_message_history()
        
        # Start WebSocket chat
        try:
            asyncio.run(self.start_chat())
        except KeyboardInterrupt:
            print("\n\nChat ended. Goodbye!")


if __name__ == "__main__":
    client = ChatClient()
    client.run()
