#!/usr/bin/env python3
"""
TUI Client for Dealership Vehicle Evaluation System.
"""
import asyncio
import websockets
import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, List
import requests


class DealershipClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
        self.token: Optional[str] = None
        self.username: Optional[str] = None
        self.websocket = None
        self.running = False
        self.current_vehicle: Optional[Dict] = None
        self.current_section: Optional[str] = None
        self.sections: List[Dict] = []
        self.unread_notifications = 0

    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')

    def print_header(self):
        print("=" * 70)
        print(" Dealership Vehicle Evaluation System".center(70))
        print("=" * 70)
        if self.username:
            notif_text = f" | Notifications: {self.unread_notifications}" if self.unread_notifications > 0 else ""
            print(f" User: {self.username}{notif_text}".ljust(70))
        if self.current_vehicle:
            vehicle_text = f" Vehicle: {self.current_vehicle['year']} {self.current_vehicle['make']} {self.current_vehicle['model']}"
            print(vehicle_text.ljust(70))
        if self.current_section:
            section_display = self.get_section_display_name(self.current_section)
            print(f" Section: {section_display}".ljust(70))
        print("=" * 70)

    def get_section_display_name(self, section_name: str) -> str:
        """Get human-readable section name from cached sections."""
        if self.sections:
            for section in self.sections:
                if section.get('section_name') == section_name:
                    icon = section.get('icon', '')
                    display = section.get('display_name', section_name)
                    return f"{icon} {display}" if icon else display
        return section_name.replace('_', ' ').title()

    def register(self, username: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/register",
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 201:
                print(f"✓ User '{username}' registered successfully!")
                return True
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                print(f"✗ Registration failed: {error_detail}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.username = username
                print(f"✓ Logged in as '{username}'")
                return True
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                print(f"✗ Login failed: {error_detail}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    def get_vehicles(self) -> List[Dict]:
        """Fetch all vehicles from the API."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/vehicles",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ Failed to fetch vehicles: {response.status_code}")
                return []
        except Exception as e:
            print(f"✗ Error: {e}")
            return []

    def get_sections(self) -> List[Dict]:
        """Fetch all sections from the API."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/sections",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
            if response.status_code == 200:
                self.sections = response.json()
                return self.sections
            else:
                print(f"✗ Failed to fetch sections")
                return []
        except Exception as e:
            print(f"✗ Error: {e}")
            return []

    def get_comments(self, vehicle_id: int, section: str) -> List[Dict]:
        """Fetch comments for a specific vehicle section."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/comments",
                params={"vehicle_id": vehicle_id, "section": section},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ Failed to fetch comments")
                return []
        except Exception as e:
            print(f"✗ Error: {e}")
            return []

    def get_notifications(self, unread_only: bool = True) -> List[Dict]:
        """Fetch notifications."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/notifications",
                params={"unread_only": unread_only},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
            if response.status_code == 200:
                notifications = response.json()
                self.unread_notifications = sum(1 for n in notifications if not n['is_read'])
                return notifications
            else:
                return []
        except Exception as e:
            print(f"✗ Error: {e}")
            return []

    def mark_notification_read(self, notification_id: int):
        """Mark a notification as read."""
        try:
            requests.patch(
                f"{self.base_url}/api/dealership/notifications/{notification_id}/read",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )
        except Exception:
            pass

    def show_vehicle_selection(self):
        """Show vehicle selection menu."""
        self.clear_screen()
        self.print_header()

        print("\n1. View Vehicles")
        print("2. View Notifications")
        print("3. Logout")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            self.show_vehicles()
        elif choice == "2":
            self.show_notifications()
        elif choice == "3":
            return False
        else:
            print("Invalid choice")
            input("Press Enter to continue...")
            self.show_vehicle_selection()

        return True

    def show_vehicles(self):
        """Display list of vehicles."""
        self.clear_screen()
        self.print_header()

        vehicles = self.get_vehicles()
        if not vehicles:
            print("\nNo vehicles found.")
            input("\nPress Enter to continue...")
            return

        print("\n--- Available Vehicles ---")
        for i, vehicle in enumerate(vehicles, 1):
            status_display = vehicle['status'].replace('_', ' ').title()
            print(f"{i}. {vehicle['year']} {vehicle['make']} {vehicle['model']} - {status_display}")
            print(f"   VIN: {vehicle['vin']}")

        print("\n0. Back")

        choice = input("\nSelect a vehicle (number): ").strip()

        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(vehicles):
                self.current_vehicle = vehicles[idx]
                self.show_section_selection()
            else:
                print("Invalid selection")
                input("Press Enter to continue...")
                self.show_vehicles()
        except ValueError:
            print("Invalid input")
            input("Press Enter to continue...")
            self.show_vehicles()

    def show_section_selection(self):
        """Display section selection for the current vehicle."""
        self.clear_screen()
        self.print_header()

        sections = self.get_sections()
        if not sections:
            print("\nNo sections found.")
            input("\nPress Enter to continue...")
            return

        print("\n--- Comments & Evaluation Sections ---")
        print("\nTip: Start with General Comments for overall vehicle notes!")
        print("Then dive into specific sections for detailed evaluation.")
        print("-" * 70)

        current_category = None
        for section in sections:
            if section['category'] != current_category:
                current_category = section['category']
                print(f"\n{current_category}:")

            icon = section.get('icon', '')
            display = f"{icon} {section['display_name']}" if icon else section['display_name']
            print(f"  {section['order_num']}. {display}")

            # Show description for general section
            if section['section_name'] == 'general' and section.get('description'):
                print(f"      ({section['description']})")

        print("\n0. Back to vehicles")

        choice = input("\nSelect a section (number): ").strip()

        if choice == "0":
            self.current_vehicle = None
            return

        try:
            section_num = int(choice)
            selected_section = next((s for s in sections if s['order_num'] == section_num), None)
            if selected_section:
                self.current_section = selected_section['section_name']
                self.show_comments_and_connect()
            else:
                print("Invalid selection")
                input("Press Enter to continue...")
                self.show_section_selection()
        except ValueError:
            print("Invalid input")
            input("Press Enter to continue...")
            self.show_section_selection()

    def show_comments_and_connect(self):
        """Show existing comments and connect to WebSocket."""
        if self.current_vehicle is None or self.current_section is None:
            print("✗ Error: No vehicle or section selected")
            return

        self.clear_screen()
        self.print_header()

        print("\n--- Comment History ---")
        comments = self.get_comments(self.current_vehicle['id'], self.current_section)

        if not comments:
            print("No comments yet. Be the first to comment!")
        else:
            for comment in comments:
                timestamp = comment['created_at'].split('T')[1].split('.')[0]
                mentions_text = ""
                if comment.get('mentioned_users'):
                    mentions_text = f" [mentioned: {', '.join(comment['mentioned_users'])}]"
                print(f"[{timestamp}] {comment['username']}: {comment['content']}{mentions_text}")

        print("-" * 70)
        print("\nConnecting to real-time chat...")
        print("Commands: /quit, /q, /exit - Exit | /back - Change section | /help - Help")
        print("-" * 70)

        input("\nPress Enter to connect...")

        # Start WebSocket chat
        try:
            asyncio.run(self.start_chat())
        except KeyboardInterrupt:
            print("\n\nDisconnected.")

        self.current_section = None
        self.show_section_selection()

    def show_notifications(self):
        """Display notifications."""
        self.clear_screen()
        self.print_header()

        print("\n--- Notifications ---")
        notifications = self.get_notifications(unread_only=False)

        if not notifications:
            print("No notifications.")
        else:
            for i, notif in enumerate(notifications, 1):
                status = "UNREAD" if not notif['is_read'] else "read"
                comment = notif['comment']
                vehicle_info = f"Vehicle ID {comment['vehicle_id']}"
                section_display = self.get_section_display_name(comment['section'])
                print(f"\n{i}. [{status}] {comment['username']} mentioned you in {vehicle_info} - {section_display}")
                print(f"   \"{comment['content'][:60]}...\" ")
                print(f"   {notif['created_at']}")

                if not notif['is_read']:
                    self.mark_notification_read(notif['id'])

        # Refresh notification count
        self.get_notifications(unread_only=True)

        input("\nPress Enter to continue...")

    async def receive_messages(self):
        """Receive and display messages from WebSocket."""
        if self.websocket is None:
            print("✗ Error: WebSocket not connected")
            return

        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "system":
                    print(f"\n[SYSTEM] {data['message']}")
                elif data["type"] == "comment":
                    timestamp = datetime.fromisoformat(data["timestamp"]).strftime("%H:%M:%S")
                    mentions_text = ""
                    if data.get('mentions'):
                        mentions_text = f" [@{', @'.join(data['mentions'])}]"
                    print(f"\n[{timestamp}] {data['username']}: {data['content']}{mentions_text}")
                elif data["type"] == "mention":
                    print(f"\n[NOTIFICATION] {data['message']}")
                    self.unread_notifications += 1
                print("> ", end="", flush=True)
        except websockets.exceptions.ConnectionClosed:
            print("\n[SYSTEM] Connection closed")
            self.running = False
        except Exception as e:
            print(f"\n[ERROR] {e}")
            self.running = False

    async def send_messages(self):
        """Send messages to WebSocket."""
        if self.websocket is None:
            print("✗ Error: WebSocket not connected")
            return

        loop = asyncio.get_event_loop()
        while self.running:
            try:
                message = await loop.run_in_executor(None, sys.stdin.readline)
                message = message.strip()

                if message:
                    if message.lower() in ['/quit', '/exit', '/q']:
                        self.running = False
                        break
                    elif message.lower() == '/back':
                        self.running = False
                        break
                    elif message == '/help':
                        print("\nCommands:")
                        print("  /quit, /exit, /q - Exit to main menu")
                        print("  /back - Change section")
                        print("  /help - Show this help")
                        print("  @username - Mention a user (they'll get notified)")
                        print("> ", end="", flush=True)
                    else:
                        await self.websocket.send(json.dumps({
                            "type": "comment",
                            "content": message
                        }))
            except Exception as e:
                print(f"\n[ERROR] {e}")
                self.running = False
                break

    async def start_chat(self):
        """Start the WebSocket chat."""
        if self.current_vehicle is None or self.current_section is None:
            print("✗ Error: No vehicle or section selected")
            return

        try:
            uri = f"{self.ws_url}/ws/chat?token={self.token}&vehicle_id={self.current_vehicle['id']}&section={self.current_section}"
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                self.running = True

                print("\nConnected! Type your comments and press Enter.")
                print("> ", end="", flush=True)

                receive_task = asyncio.create_task(self.receive_messages())
                send_task = asyncio.create_task(self.send_messages())

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
            input("\nPress Enter to login...")

        if not self.login(username, password):
            input("\nPress Enter to exit...")
            return

        # Get initial notification count
        self.get_notifications(unread_only=True)

        # Main loop
        while True:
            if not self.show_vehicle_selection():
                break

        print("\nGoodbye!")


if __name__ == "__main__":
    client = DealershipClient()
    client.run()
