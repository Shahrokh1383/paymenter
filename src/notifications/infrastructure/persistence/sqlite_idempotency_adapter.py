import sqlite3
from src.notifications.domain.ports.idempotency_port import IdempotencyPort
from src.common.infrastructure.database import DB_PATH

class SqliteIdempotencyAdapter(IdempotencyPort):
    """Infrastructure adapter for idempotency checking using SQLite."""
    
    def is_processed(self, event_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            return cursor.fetchone() is not None

    def mark_as_processed(self, event_id: str) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)", (event_id,))
            conn.commit()