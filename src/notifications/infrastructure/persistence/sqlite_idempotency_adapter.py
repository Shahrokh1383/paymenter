import sqlite3
from typing import Callable
from src.notifications.domain.ports.idempotency_port import IdempotencyPort
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

class SqliteIdempotencyAdapter(IdempotencyPort):
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        self._connection_factory = connection_factory

    def _get_connection(self) -> sqlite3.Connection:
        """Use ambient connection if available, else create a new one."""
        ambient = SqliteUnitOfWork.get_current_connection()
        return ambient if ambient is not None else self._connection_factory()

    def _close_if_standalone(self, conn: sqlite3.Connection):
        """Only close connections that we created ourselves."""
        if conn is not SqliteUnitOfWork.get_current_connection():
            conn.close()

    def is_processed(self, event_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            return cursor.fetchone() is not None
        finally:
            self._close_if_standalone(conn)

    def mark_as_processed(self, event_id: str) -> None:
        conn = self._get_connection()
        try:
            conn.execute("INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)", (event_id,))
            if conn is not SqliteUnitOfWork.get_current_connection():
                conn.commit()
        finally:
            self._close_if_standalone(conn)