"""
Event system for decoupled application components.

The event bus allows different parts of the application to communicate
without direct dependencies.
"""
from app.events.bus import event_bus

__all__ = ['event_bus']
