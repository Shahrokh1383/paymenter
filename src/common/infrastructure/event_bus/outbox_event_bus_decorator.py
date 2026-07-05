import json
import dataclasses
import sqlite3
import decimal
from typing import Any, Callable, Dict, List
from src.common.domain.ports.event_bus import EventBus
from src.common.infrastructure.database import DB_PATH
from src.common.infrastructure.persistence.outbox_relay_worker import OutboxRelayWorker

class OutboxEventBusDecorator(EventBus):
    """
    Decorator that implements the Approximate ACID Outbox Pattern.
    Intercepts publish calls, saves to DB to prevent phantom events (EC-3),
    and dispatches in a background thread to prevent HTTP blocking.
    """
    
    def __init__(self, inner_bus: EventBus):
        self._inner_bus = inner_bus
        self._subscribers: Dict[type, List[Callable]] = {}
        self._worker = OutboxRelayWorker(inner_bus)
        # Start the background relay worker
        self._worker.start()

    def subscribe(self, event_type: type, handler: Callable) -> None:
        # Subscriptions still go to the inner bus for actual execution
        self._inner_bus.subscribe(event_type, handler)

    class _DomainEventEncoder(json.JSONEncoder):
        """Custom encoder to handle Domain Value Objects safely at the infrastructure boundary."""
        def default(self, obj):
            if isinstance(obj, decimal.Decimal):
                return str(obj)
            return super().default(obj)

    def publish(self, event: Any) -> None:
        event_type = type(event).__name__
        
        payload = json.dumps(dataclasses.asdict(event), cls=self._DomainEventEncoder)
        
        try:
            with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(
                    "INSERT INTO outbox_messages (event_type, payload) VALUES (?, ?)",
                    (event_type, payload)
                )
                conn.commit()
        except Exception as e:
            print(f"[OUTBOX CRITICAL] Failed to persist event to outbox: {e}")
            raise e

        # 2. Notify background worker to process immediately (Non-blocking)
        self._worker.trigger_processing()

    def flush(self) -> None:
        self._worker._process_pending_messages()