"""
Event handlers for application events.

Import this module to register all event handlers at application startup.
"""

# Import handlers to register them with the event bus
# The @event_bus.on() decorators register handlers automatically on import
from app.events.handlers import notifications
from app.events.handlers import websocket_broadcast

__all__ = ['notifications', 'websocket_broadcast']
