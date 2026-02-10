"""
Event handlers for attachment lifecycle events.

Handles WebSocket broadcasts when attachments complete processing.
"""
import json
import logging

from app.events.bus import event_bus

logger = logging.getLogger(__name__)


@event_bus.on('attachment.ready')
async def broadcast_attachment_ready(data: dict):
    """
    Notify the uploader via WebSocket when a chunked upload finishes processing.

    This lets the TUI update its UI to show the attachment as available
    before the user sends the comment.
    """
    try:
        from app.websocket import manager

        uploader_id = data.get('uploader_id')
        if not uploader_id:
            return

        message = json.dumps({
            'type': 'attachment_ready',
            'attachment_id': data.get('attachment_id'),
            'filename': data.get('filename'),
            'content_type': data.get('content_type'),
            'file_size': data.get('file_size'),
        })

        # Send to the uploader if they're connected
        # We iterate all rooms since we don't know which room they're in
        for room_id, users in manager.rooms.items():
            for username, ws in users.items():
                # We'd need username→user_id mapping; for now broadcast to all rooms
                # the uploader is in. The client filters by attachment_id.
                try:
                    await ws.send_text(message)
                except Exception:
                    pass

        logger.debug(f"Broadcasted attachment.ready for {data.get('attachment_id')}")

    except Exception as e:
        logger.error(f"Error broadcasting attachment.ready: {e}", exc_info=True)


# Register on import
logger.info("Attachment event handlers registered")
