#!/usr/bin/env python3
"""
TUI Client for Dealership Vehicle Evaluation System.
Supports real-time comments, @mentions, and file attachments.
"""
import asyncio
import websockets
import json
import sys
import os
import math
from datetime import datetime
from typing import Optional, Dict, List
import requests


SIMPLE_UPLOAD_LIMIT = 5 * 1024 * 1024  # 5MB — matches server limit
CHUNK_SIZE = 100 * 1024  # 100KB per chunk

# Extension → MIME type map (must match server's ALLOWED_CONTENT_TYPES)
EXT_TO_CONTENT_TYPE = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp',
    '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
    '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
    '.pdf': 'application/pdf',
}


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


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
        # Pending attachments: uploaded but not yet linked to a comment
        self.pending_attachments: List[Dict] = []

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

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
                print(f"  User '{username}' registered successfully!")
                return True
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                print(f"  Registration failed: {error_detail}")
                return False
        except Exception as e:
            print(f"  Error: {e}")
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
                print(f"  Logged in as '{username}'")
                return True
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                print(f"  Login failed: {error_detail}")
                return False
        except Exception as e:
            print(f"  Error: {e}")
            return False

    def get_vehicles(self) -> List[Dict]:
        """Fetch all vehicles from the API."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/vehicles",
                headers=self._auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  Failed to fetch vehicles: {response.status_code}")
                return []
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def get_sections(self) -> List[Dict]:
        """Fetch all sections from the API."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/sections",
                headers=self._auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                self.sections = response.json()
                return self.sections
            else:
                print(f"  Failed to fetch sections")
                return []
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def get_comments(self, vehicle_id: int, section: str) -> List[Dict]:
        """Fetch comments for a specific vehicle section."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/comments",
                params={"vehicle_id": vehicle_id, "section": section},
                headers=self._auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  Failed to fetch comments")
                return []
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def get_notifications(self, unread_only: bool = True) -> List[Dict]:
        """Fetch notifications."""
        try:
            response = requests.get(
                f"{self.base_url}/api/dealership/notifications",
                params={"unread_only": unread_only},
                headers=self._auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                notifications = response.json()
                self.unread_notifications = sum(1 for n in notifications if not n['is_read'])
                return notifications
            else:
                return []
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def mark_notification_read(self, notification_id: int):
        """Mark a notification as read."""
        try:
            requests.patch(
                f"{self.base_url}/api/dealership/notifications/{notification_id}/read",
                headers=self._auth_headers(),
                timeout=5
            )
        except Exception:
            pass

    # ─── Attachment Methods ────────────────────────────────────────────

    def upload_attachment_simple(self, filepath: str) -> Optional[Dict]:
        """Upload a small file (< 5MB) in a single request."""
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        content_type = EXT_TO_CONTENT_TYPE.get(ext, 'application/octet-stream')
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(
                    f"{self.base_url}/api/attachments/upload",
                    headers=self._auth_headers(),
                    files={"file": (filename, f, content_type)},
                    timeout=30
                )
            if response.status_code == 201:
                return response.json()
            else:
                detail = response.json().get('detail', 'Upload failed')
                print(f"\n  Upload failed: {detail}")
                return None
        except Exception as e:
            print(f"\n  Upload error: {e}")
            return None

    def upload_attachment_chunked(self, filepath: str) -> Optional[Dict]:
        """Upload a large file using chunked upload protocol."""
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)

        ext = os.path.splitext(filename)[1].lower()
        content_type = EXT_TO_CONTENT_TYPE.get(ext, 'application/octet-stream')

        total_chunks = math.ceil(file_size / CHUNK_SIZE)

        # Step 1: Initialize
        try:
            resp = requests.post(
                f"{self.base_url}/api/attachments/upload/init",
                headers=self._auth_headers(),
                json={
                    "filename": filename,
                    "content_type": content_type,
                    "total_size": file_size,
                    "total_chunks": total_chunks,
                },
                timeout=10
            )
            if resp.status_code != 201:
                detail = resp.json().get('detail', 'Init failed')
                print(f"\n  Chunked init failed: {detail}")
                return None
            init_data = resp.json()
            upload_id = init_data['upload_id']
        except Exception as e:
            print(f"\n  Chunked init error: {e}")
            return None

        # Step 2: Upload chunks
        try:
            with open(filepath, 'rb') as f:
                for i in range(total_chunks):
                    chunk_data = f.read(CHUNK_SIZE)
                    if not chunk_data:
                        break

                    resp = requests.patch(
                        f"{self.base_url}/api/attachments/upload/{upload_id}/chunk/{i}",
                        headers=self._auth_headers(),
                        files={"file": (f"chunk_{i}", chunk_data)},
                        timeout=30
                    )
                    if resp.status_code != 200:
                        detail = resp.json().get('detail', 'Chunk upload failed')
                        print(f"\n  Chunk {i} failed: {detail}")
                        return None

                    # Progress bar
                    progress = (i + 1) / total_chunks
                    bar_len = 30
                    filled = int(bar_len * progress)
                    bar = "#" * filled + "-" * (bar_len - filled)
                    pct = progress * 100
                    print(f"\r  Uploading [{bar}] {pct:.0f}% ({i+1}/{total_chunks})", end="", flush=True)

            print()  # newline after progress bar
        except Exception as e:
            print(f"\n  Chunk upload error: {e}")
            return None

        # Step 3: Complete
        try:
            resp = requests.post(
                f"{self.base_url}/api/attachments/upload/{upload_id}/complete",
                headers=self._auth_headers(),
                timeout=60
            )
            if resp.status_code == 200:
                return resp.json().get('attachment')
            else:
                detail = resp.json().get('detail', 'Complete failed')
                print(f"\n  Complete failed: {detail}")
                return None
        except Exception as e:
            print(f"\n  Complete error: {e}")
            return None

    def upload_attachment(self, filepath: str) -> Optional[Dict]:
        """Upload a file — picks simple or chunked based on size."""
        filepath = os.path.expanduser(filepath)

        if not os.path.isfile(filepath):
            print(f"\n  File not found: {filepath}")
            return None

        file_size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)
        size_str = format_file_size(file_size)

        print(f"\n  Uploading: {filename} ({size_str})")

        if file_size <= SIMPLE_UPLOAD_LIMIT:
            result = self.upload_attachment_simple(filepath)
        else:
            result = self.upload_attachment_chunked(filepath)

        if result:
            self.pending_attachments.append(result)
            count = len(self.pending_attachments)
            print(f"  Uploaded! [{count} attachment(s) pending]")
            print(f"  ID: {result['id']}")
            print(f"  Your next comment will include all pending attachments.")
        return result

    def download_attachment(self, attachment_id: str, save_dir: str = ".") -> bool:
        """Download an attachment to the local filesystem."""
        try:
            # Get metadata first
            meta_resp = requests.get(
                f"{self.base_url}/api/attachments/{attachment_id}",
                headers=self._auth_headers(),
                timeout=5
            )
            if meta_resp.status_code != 200:
                print(f"\n  Attachment not found: {attachment_id}")
                return False

            meta = meta_resp.json()
            filename = meta['filename']
            size_str = format_file_size(meta['file_size'])

            print(f"\n  Downloading: {filename} ({size_str})")

            # Download
            dl_resp = requests.get(
                f"{self.base_url}/api/attachments/{attachment_id}/download",
                headers=self._auth_headers(),
                timeout=120,
                stream=True
            )
            if dl_resp.status_code != 200:
                detail = dl_resp.json().get('detail', 'Download failed')
                print(f"  Download failed: {detail}")
                return False

            save_path = os.path.join(save_dir, filename)
            # Avoid overwriting — append (1), (2), etc.
            base, ext = os.path.splitext(save_path)
            counter = 1
            while os.path.exists(save_path):
                save_path = f"{base} ({counter}){ext}"
                counter += 1

            with open(save_path, 'wb') as f:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  Saved to: {save_path}")
            return True

        except Exception as e:
            print(f"\n  Download error: {e}")
            return False

    # ─── Display Methods ───────────────────────────────────────────────

    @staticmethod
    def _format_comment(comment: Dict) -> str:
        """Format a comment with optional attachment indicators."""
        timestamp = comment['created_at'].split('T')[1].split('.')[0]
        mentions_text = ""
        if comment.get('mentioned_users'):
            mentions_text = f" [mentioned: {', '.join(comment['mentioned_users'])}]"

        lines = [f"[{timestamp}] {comment['username']}: {comment['content']}{mentions_text}"]

        attachments = comment.get('attachments', [])
        for att in attachments:
            size_str = format_file_size(att['file_size'])
            lines.append(f"         [ATTACHMENT] {att['filename']} ({size_str}) id:{att['id'][:8]}")

        return "\n".join(lines)

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
            print("  Error: No vehicle or section selected")
            return

        self.clear_screen()
        self.print_header()

        print("\n--- Comment History ---")
        comments = self.get_comments(self.current_vehicle['id'], self.current_section)

        if not comments:
            print("No comments yet. Be the first to comment!")
        else:
            for comment in comments:
                print(self._format_comment(comment))

        print("-" * 70)
        print("\nConnecting to real-time chat...")
        print("Commands:")
        print("  /attach <path>       - Upload a file attachment")
        print("  /pending             - Show pending attachments")
        print("  /clear               - Clear pending attachments")
        print("  /download <id>       - Download attachment by ID (first 8 chars)")
        print("  /back                - Change section")
        print("  /quit, /q, /exit     - Exit")
        print("  /help                - Show all commands")
        print("  @username            - Mention a user")
        print("-" * 70)

        input("\nPress Enter to connect...")

        # Reset pending attachments for this session
        self.pending_attachments = []

        # Start WebSocket chat
        try:
            asyncio.run(self.start_chat())
        except KeyboardInterrupt:
            print("\n\nDisconnected.")

        self.pending_attachments = []
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

    # ─── WebSocket Chat ────────────────────────────────────────────────

    async def receive_messages(self):
        """Receive and display messages from WebSocket."""
        if self.websocket is None:
            print("  Error: WebSocket not connected")
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
                    # Show attachments inline
                    for att in data.get('attachments', []):
                        size_str = format_file_size(att.get('file_size', 0))
                        print(f"         [ATTACHMENT] {att['filename']} ({size_str}) id:{att['id'][:8]}")
                elif data["type"] == "mention":
                    print(f"\n[NOTIFICATION] {data['message']}")
                    self.unread_notifications += 1
                elif data["type"] == "attachment_ready":
                    att_id = data.get('attachment_id')
                    fname = data.get('filename')
                    # Update the pending attachment's status so it gets linked on next comment
                    for att in self.pending_attachments:
                        if att['id'] == att_id:
                            att['status'] = 'ready'
                            break
                    print(f"\n[UPLOAD READY] {fname} is ready")
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
            print("  Error: WebSocket not connected")
            return

        loop = asyncio.get_event_loop()
        while self.running:
            try:
                message = await loop.run_in_executor(None, sys.stdin.readline)
                message = message.strip()

                if not message:
                    continue

                # ── Command handling ──────────────────────────
                if message.lower() in ['/quit', '/exit', '/q']:
                    self.running = False
                    break
                elif message.lower() == '/back':
                    self.running = False
                    break

                elif message.lower() == '/help':
                    print("\nCommands:")
                    print("  /attach <path>       - Upload a file (image, video, audio, PDF)")
                    print("  /pending             - Show attachments waiting to be sent")
                    print("  /clear               - Remove all pending attachments")
                    print("  /download <id>       - Download attachment (use first 8 chars of ID)")
                    print("  /quit, /exit, /q     - Exit to main menu")
                    print("  /back                - Change section")
                    print("  @username            - Mention a user")
                    print("> ", end="", flush=True)

                elif message.lower().startswith('/attach '):
                    filepath = message[8:].strip()
                    # Run upload in executor to avoid blocking
                    await loop.run_in_executor(None, self.upload_attachment, filepath)
                    print("> ", end="", flush=True)

                elif message.lower() == '/pending':
                    if not self.pending_attachments:
                        print("\n  No pending attachments.")
                    else:
                        print(f"\n  Pending attachments ({len(self.pending_attachments)}):")
                        for att in self.pending_attachments:
                            size_str = format_file_size(att['file_size'])
                            print(f"    - {att['filename']} ({size_str}) [{att['status']}] id:{att['id'][:8]}")
                        print("  These will be attached to your next comment.")
                    print("> ", end="", flush=True)

                elif message.lower() == '/clear':
                    count = len(self.pending_attachments)
                    self.pending_attachments = []
                    print(f"\n  Cleared {count} pending attachment(s).")
                    print("> ", end="", flush=True)

                elif message.lower().startswith('/download '):
                    att_id_prefix = message[10:].strip()
                    # Find full ID from prefix
                    full_id = self._resolve_attachment_id(att_id_prefix)
                    if full_id:
                        await loop.run_in_executor(None, self.download_attachment, full_id)
                    else:
                        print(f"\n  Could not resolve attachment ID: {att_id_prefix}")
                        print("  Use the full ID or first 8 characters shown in [ATTACHMENT] lines.")
                    print("> ", end="", flush=True)

                # ── Regular comment ───────────────────────────
                else:
                    payload: Dict = {
                        "type": "comment",
                        "content": message,
                    }
                    # Attach pending files — verify status with server to avoid race conditions
                    if self.pending_attachments:
                        ready_ids = []
                        not_ready = []
                        for att in self.pending_attachments:
                            # Ask the server for the current status instead of trusting local state
                            server_status = await loop.run_in_executor(
                                None, self._check_attachment_status, att['id']
                            )
                            if server_status == 'ready':
                                ready_ids.append(att['id'])
                            else:
                                not_ready.append(att)
                        if ready_ids:
                            payload["attachment_ids"] = ready_ids
                            print(f"\n  Attaching {len(ready_ids)} file(s) to comment...")
                        if not_ready:
                            print(f"\n  Warning: {len(not_ready)} attachment(s) not ready yet, skipping them.")
                        self.pending_attachments = []

                    await self.websocket.send(json.dumps(payload))

            except Exception as e:
                print(f"\n[ERROR] {e}")
                self.running = False
                break

    def _check_attachment_status(self, attachment_id: str) -> Optional[str]:
        """Query the server for the current status of an attachment."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/attachments/{attachment_id}",
                headers=self._auth_headers(),
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json().get('status')
        except Exception:
            pass
        return None

    def _resolve_attachment_id(self, prefix: str) -> Optional[str]:
        """Try to find a full attachment ID from a short prefix, using recent comments."""
        # Check pending attachments first
        for att in self.pending_attachments:
            if att['id'].startswith(prefix):
                return att['id']
        # If we have current vehicle/section, check comment history
        if self.current_vehicle and self.current_section:
            comments = self.get_comments(self.current_vehicle['id'], self.current_section)
            for comment in comments:
                for att in comment.get('attachments', []):
                    if att['id'].startswith(prefix):
                        return att['id']
        # Last resort: try it as-is (maybe they pasted the full UUID)
        if len(prefix) == 36:
            return prefix
        return None

    async def start_chat(self):
        """Start the WebSocket chat."""
        if self.current_vehicle is None or self.current_section is None:
            print("  Error: No vehicle or section selected")
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
            print(f"\n  Connection error: {e}")

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
