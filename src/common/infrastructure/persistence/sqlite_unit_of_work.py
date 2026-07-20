import sqlite3
import contextvars
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.database import DB_PATH

# ContextVar to hold the active connection for ambient transactions
_current_conn = contextvars.ContextVar("current_conn", default=None)
_nesting_level = contextvars.ContextVar("nesting_level", default=0)

class SqliteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork pattern with Ambient Transaction support."""
    
    def __enter__(self):
        conn = _current_conn.get()
        if conn is None:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode=WAL;")
            _current_conn.set(conn)
            
        self.conn = conn
        _nesting_level.set(_nesting_level.get() + 1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _nesting_level.set(_nesting_level.get() - 1)
        if _nesting_level.get() == 0:
            try:
                if exc_type is None:
                    self.commit()
                else:
                    self.rollback()
            finally:
                self.conn.close()
                _current_conn.set(None)
                self.conn = None

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()