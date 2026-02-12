"""
WebSocket broadcasting handlers.

This module handles real-time WebSocket broadcasts when comments are created.
It listens to 'comment.created' events and broadcasts to appropriate rooms.
"""
import json
from app.events.bus import event_bus
import logging

logger = logging.getLogger(__name__)


@event_bus.on('comment.created')
async def broadcast_comment_to_room(data: dict):
    """
    Broadcast new comment to all users in the vehicle+section room.

    This handler is triggered when a 'comment.created' event is emitted.
    It sends the comment to all WebSocket clients currently viewing the
    same vehicle and section.

    Event data expected:
        - comment_id: ID of the created comment
        - username: Username of the comment author
        - content: Comment content (decrypted)
        - vehicle_id: ID of the vehicle
        - section: Section name
        - timestamp: ISO format timestamp
        - mentions: List of mentioned usernames

    Args:
        data: Event data dictionary containing comment information
    """
    try:
        # Import here to avoid circular imports
        from app.websocket import manager

        vehicle_id = data.get('vehicle_id')
        section = data.get('section')

        if not vehicle_id or not section:
            logger.warning("Missing vehicle_id or section in comment.created event")
            return

        # Generate room ID
        room_id = manager.get_room_id(vehicle_id, section)

        # Prepare broadcast message
        broadcast_data = json.dumps({
            'type': 'comment',
            'comment_id': data.get('comment_id'),
            'username': data.get('username'),
            'content': data.get('content'),
            'vehicle_id': vehicle_id,
            'section': section,
            'timestamp': data.get('timestamp'),
            'mentions': data.get('mentions', []),
            'attachments': data.get('attachments', []),
        })

        # Broadcast to room
        await manager.broadcast_to_room(room_id, broadcast_data)
        logger.debug(f"Broadcasted comment {data.get('comment_id')} to room {room_id}")

    except Exception as e:
        logger.error(f"Error broadcasting comment: {e}", exc_info=True)


@event_bus.on('comment.created')
async def send_mention_notifications(data: dict):
    """
    Send real-time WebSocket notifications to mentioned users.

    This handler sends personal WebSocket messages to users who were
    @mentioned in a comment, if they are currently connected.

    Event data expected:
        - comment_id: ID of the created comment
        - username: Username of the comment author
        - content: Comment content
        - vehicle_id: ID of the vehicle
        - section: Section name
        - vehicle_make: Vehicle make (e.g., "Toyota")
        - vehicle_model: Vehicle model (e.g., "Camry")
        - mentions: List of mentioned usernames

    Args:
        data: Event data dictionary containing comment information
    """
    try:
        # Import here to avoid circular imports
        from app.websocket import manager
        from app.events.handlers.notifications import extract_mentions

        mentions = data.get('mentions', [])
        if not mentions:
            # Extract mentions if not provided
            mentions = extract_mentions(data.get('content', ''))

        if not mentions:
            return

        username = data.get('username')
        vehicle_id = data.get('vehicle_id')
        section = data.get('section')
        vehicle_make = data.get('vehicle_make', 'Vehicle')
        vehicle_model = data.get('vehicle_model', '')

        vehicle_display = f"{vehicle_make} {vehicle_model}".strip()

        # Send personal message to each mentioned user
        for mentioned_username in mentions:
            # Don't send to the author
            if mentioned_username == username:
                continue

            notification_message = json.dumps({
                'type': 'mention',
                'message': f"You were mentioned by {username} in {vehicle_display} - {section}",
                'comment_id': data.get('comment_id'),
                'vehicle_id': vehicle_id,
                'section': section
            })

            await manager.send_personal_message(notification_message, mentioned_username)
            logger.debug(f"Sent mention notification to @{mentioned_username}")

    except Exception as e:
        logger.error(f"Error sending mention notifications: {e}", exc_info=True)


# This module is imported at startup to register the handlers
logger.info("WebSocket broadcast handlers registered")
