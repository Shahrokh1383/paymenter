import sqlite3
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.database import DB_PATH

class SqliteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork pattern."""
    
    def __init__(self):
        self.conn = None
        self._nesting_level = 0

    def __enter__(self):
        if self._nesting_level == 0:
            self.conn = sqlite3.connect(DB_PATH, timeout=10.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON;")
        self._nesting_level += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._nesting_level -= 1
        if self._nesting_level == 0:
            if self.conn:
                try:
                    if exc_type is None:
                        self.commit()
                    else:
                        self.rollback()
                finally:
                    self.conn.close()
                    self.conn = None

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()