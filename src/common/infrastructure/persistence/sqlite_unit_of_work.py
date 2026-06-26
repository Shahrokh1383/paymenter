import sqlite3
import os
from src.common.domain.ports.unit_of_work import UnitOfWork

# Pointing to the existing database during the Strangler Fig migration phase
DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'database', 'storage')
DB_PATH = os.path.abspath(os.path.join(DB_DIR, 'paymenter.db'))

class SqliteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork pattern."""
    
    def __init__(self):
        self.conn = None

    def __enter__(self):
        os.makedirs(DB_PATH.replace('paymenter.db', ''), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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