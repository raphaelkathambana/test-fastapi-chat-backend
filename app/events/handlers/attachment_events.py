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

        uploader_username = data.get('uploader_username')
        if not uploader_username:
            return

        message = json.dumps({
            'type': 'attachment_ready',
            'attachment_id': data.get('attachment_id'),
            'filename': data.get('filename'),
            'content_type': data.get('content_type'),
            'file_size': data.get('file_size'),
        })

        # Send only to the uploader, not to all users
        await manager.send_personal_message(message, uploader_username)

        logger.debug(f"Sent attachment.ready to {uploader_username} for {data.get('attachment_id')}")

    except Exception as e:
        logger.error(f"Error broadcasting attachment.ready: {e}", exc_info=True)


# Register on import
logger.info("Attachment event handlers registered")
