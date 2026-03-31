"""
In-memory Event Bus for domain events.

This is a simple in-memory implementation. For production with multiple instances,
consider Redis pub/sub or a message broker like RabbitMQ/Kafka.
"""

import logging
from typing import Dict, List, Type, Callable, Awaitable
from core.domain.events.base import DomainEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    In-memory event bus for publishing and subscribing to domain events.
    
    Usage:
        # Subscribe to event
        event_bus.subscribe(DocumentUploaded, handle_document_uploaded)
        
        # Publish event
        await event_bus.publish(DocumentUploaded(document_id="123", ...))
    """
    
    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], Awaitable[None]]]] = {}
        self._event_history: List[DomainEvent] = []  # For debugging
        self._max_history = 1000  # Keep last 1000 events
    
    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]]
    ):
        """
        Subscribe a handler to an event type.
        
        Args:
            event_type: The domain event class to subscribe to
            handler: Async function that handles the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        logger.info(f"✅ Subscribed handler {handler.__name__} to {event_type.__name__}")
    
    async def publish(self, event: DomainEvent):
        """
        Publish an event to all subscribed handlers.
        
        Args:
            event: The domain event to publish
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        
        if not handlers:
            logger.debug(f"No handlers for event {event_type.__name__}")
            return
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Execute all handlers
        logger.info(f"📤 Publishing event: {event_type.__name__} (id={event.event_id})")
        
        for handler in handlers:
            try:
                await handler(event)
                logger.debug(f"✅ Handler {handler.__name__} processed {event_type.__name__}")
            except Exception as e:
                logger.error(
                    f"❌ Handler {handler.__name__} failed for {event_type.__name__}: {e}",
                    exc_info=True
                )
                # Continue with other handlers even if one fails
    
    def get_event_history(self, event_type: Type[DomainEvent] = None) -> List[DomainEvent]:
        """
        Get event history for debugging.
        
        Args:
            event_type: Optional filter by event type
        
        Returns:
            List of events
        """
        if event_type:
            return [e for e in self._event_history if isinstance(e, event_type)]
        return self._event_history.copy()
    
    def clear_history(self):
        """Clear event history."""
        self._event_history.clear()
    
    def get_subscriber_count(self, event_type: Type[DomainEvent]) -> int:
        """Get number of subscribers for an event type."""
        return len(self._handlers.get(event_type, []))


# Global event bus instance
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return event_bus
