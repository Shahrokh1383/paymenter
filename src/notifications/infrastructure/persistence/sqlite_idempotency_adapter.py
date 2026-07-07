import sqlite3
from typing import Callable
from src.notifications.domain.ports.idempotency_port import IdempotencyPort
class SqliteIdempotencyAdapter(IdempotencyPort):
    """Infrastructure adapter for idempotency checking using SQLite."""
    
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        """
        Inject connection factory to respect Hexagonal Architecture.
        The factory must return a properly configured sqlite3.Connection.
        """
        self._connection_factory = connection_factory

    def is_processed(self, event_id: str) -> bool:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def mark_as_processed(self, event_id: str) -> None:
        conn = self._connection_factory()
        try:
            conn.execute("INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)", (event_id,))
            conn.commit()
        finally:
            conn.close()