"""
Simple in-app event bus for decoupled event handling.

This event bus allows components to emit events and other components
to listen and react to those events without tight coupling.

Example:
    # Register a handler
    @event_bus.on('comment.created')
    async def handle_comment(data: dict):
        print(f"Comment created: {data['comment_id']}")

    # Emit an event
    await event_bus.emit('comment.created', {'comment_id': 123})
"""
from typing import Callable, Dict, List, Any
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple in-memory event bus for publish-subscribe pattern.

    Thread-safe for async operations. Handlers are called sequentially
    in the order they were registered.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    def on(self, event_name: str):
        """
        Decorator to register an event handler.

        Args:
            event_name: Name of the event to listen for

        Example:
            @event_bus.on('user.created')
            async def handle_user_created(data: dict):
                print(f"User {data['username']} created")
        """
        def decorator(handler: Callable):
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            self._handlers[event_name].append(handler)
            logger.debug(
                f"Registered handler {handler.__name__} for event '{event_name}'")
            return handler
        return decorator

    def register(self, event_name: str, handler: Callable):
        """
        Register an event handler programmatically (alternative to decorator).

        Args:
            event_name: Name of the event to listen for
            handler: Async function to call when event is emitted
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.debug(
            f"Registered handler {handler.__name__} for event '{event_name}'")

    async def emit(self, event_name: str, data: Any = None):
        """
        Emit an event to all registered handlers.

        Handlers are called sequentially. If a handler raises an exception,
        it's logged but doesn't prevent other handlers from running.

        Args:
            event_name: Name of the event to emit
            data: Data to pass to handlers (typically a dict)

        Example:
            await event_bus.emit('comment.created', {
                'comment_id': 123,
                'user_id': 456,
                'content': 'Hello @bob'
            })
        """
        if event_name not in self._handlers:
            logger.debug(f"No handlers registered for event '{event_name}'")
            return

        handlers = self._handlers[event_name]
        logger.debug(
            f"Emitting event '{event_name}' to {len(handlers)} handler(s)")

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(
                    f"Error in handler {handler.__name__} for event '{event_name}': {e}",
                    exc_info=True
                )

    def remove_handler(self, event_name: str, handler: Callable):
        """Remove a specific handler from an event."""
        if event_name in self._handlers:
            try:
                self._handlers[event_name].remove(handler)
                logger.debug(
                    f"Removed handler {handler.__name__} from event '{event_name}'")
            except ValueError:
                pass

    def clear_handlers(self, event_name: str | None = None):
        """
        Clear handlers for a specific event or all events.

        Args:
            event_name: Event to clear handlers for. If None, clears all.
        """
        if event_name:
            self._handlers[event_name] = []
            logger.debug(f"Cleared all handlers for event '{event_name}'")
        else:
            self._handlers = {}
            logger.debug("Cleared all event handlers")

    def get_events(self) -> List[str]:
        """Get list of all events that have registered handlers."""
        return list(self._handlers.keys())

    def get_handler_count(self, event_name: str) -> int:
        """Get number of handlers registered for an event."""
        return len(self._handlers.get(event_name, []))


# Global event bus instance
event_bus = EventBus()
