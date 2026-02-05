"""
Notification handlers for @mention events.

This module handles creating database notifications when users are mentioned
in comments. It listens to 'comment.created' events and processes @mentions.
"""
import re
from typing import List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import User, Notification
from app.events.bus import event_bus
import logging

logger = logging.getLogger(__name__)


def extract_mentions(content: str) -> List[str]:
    """
    Extract @username mentions from content using regex.

    Matches @username pattern where username can contain:
    - Letters (a-z, A-Z)
    - Numbers (0-9)
    - Underscores (_)
    - Hyphens (-)

    Args:
        content: The text content to search for mentions

    Returns:
        List of unique usernames mentioned (without @ symbol)

    Example:
        >>> extract_mentions("Hello @alice and @bob")
        ['alice', 'bob']

        >>> extract_mentions("Check this @john-doe and @jane_smith")
        ['john-doe', 'jane_smith']
    """
    pattern = r'@([a-zA-Z0-9_-]+)'
    mentions = re.findall(pattern, content)
    return list(set(mentions))  # Remove duplicates


@event_bus.on('comment.created')
async def create_mention_notifications(data: dict):
    """
    Create database notifications for @mentioned users.

    This handler is triggered when a 'comment.created' event is emitted.
    It extracts @mentions from the comment content and creates notification
    records in the database for each mentioned user.

    Event data expected:
        - comment_id: ID of the created comment
        - content: Decrypted comment content
        - author_id: ID of the user who created the comment
        - vehicle_id: ID of the vehicle
        - section: Section name

    Security:
        - Only creates notifications for existing users
        - Prevents self-mentions (user can't notify themselves)
        - Uses database session for atomic operations

    Args:
        data: Event data dictionary containing comment information
    """
    db: Session = SessionLocal()

    try:
        comment_id = data.get('comment_id')
        content = data.get('content')
        author_id = data.get('author_id')

        if not all([comment_id, content, author_id]):
            logger.warning("Missing required fields in comment.created event data")
            return

        # Extract @mentions from content
        mentioned_usernames = extract_mentions(content)

        if not mentioned_usernames:
            logger.debug(f"No mentions found in comment {comment_id}")
            return

        logger.info(f"Processing {len(mentioned_usernames)} mention(s) from comment {comment_id}")

        # Create notification for each mentioned user
        notifications_created = 0
        for username in mentioned_usernames:
            # Look up the mentioned user
            mentioned_user = db.query(User).filter(User.username == username).first()

            if not mentioned_user:
                logger.debug(f"User @{username} not found, skipping notification")
                continue

            # Don't notify if user mentions themselves
            if mentioned_user.id == author_id:
                logger.debug(f"User mentioned themselves, skipping self-notification")
                continue

            # Check if notification already exists (prevent duplicates)
            existing = db.query(Notification).filter(
                Notification.recipient_id == mentioned_user.id,
                Notification.comment_id == comment_id
            ).first()

            if existing:
                logger.debug(f"Notification already exists for user {username}, skipping")
                continue

            # Create notification
            notification = Notification(
                recipient_id=mentioned_user.id,
                comment_id=comment_id,
                is_read=False
            )
            db.add(notification)
            notifications_created += 1
            logger.debug(f"Created notification for user @{username}")

        # Commit all notifications at once
        if notifications_created > 0:
            db.commit()
            logger.info(f"Created {notifications_created} notification(s) for comment {comment_id}")
        else:
            logger.debug(f"No new notifications created for comment {comment_id}")

    except Exception as e:
        logger.error(f"Error creating mention notifications: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# This module is imported at startup to register the handlers
logger.info("Notification handlers registered")
