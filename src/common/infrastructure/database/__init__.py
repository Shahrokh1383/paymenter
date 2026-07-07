import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(__file__), 'storage')
DB_PATH = os.path.join(DB_DIR, 'paymenter.db')

from src.common.infrastructure.database.schemas.identity.identity import IDENTITY_SCHEMA
from src.common.infrastructure.database.schemas.ledger.ledger import LEDGER_SCHEMA
from src.common.infrastructure.database.schemas.checkout.checkout import CHECKOUT_SCHEMA
from src.common.infrastructure.database.schemas.notifications.notifications import NOTIFICATIONS_SCHEMA

def create_connection() -> sqlite3.Connection:
    """
    Factory function to create properly configured SQLite connections.
    Ensures consistent PRAGMA settings across all infrastructure adapters (Rule 6).
    """
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

class Database:
    @staticmethod
    def initialize() -> None:
        """
        Strictly orchestrates schema creation. 
        No data seeding is allowed here to protect Domain Invariants (Rule 4).
        """
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
        
        conn = create_connection()
        cursor = conn.cursor()
        
        master_schema = (
            IDENTITY_SCHEMA + 
            LEDGER_SCHEMA + 
            CHECKOUT_SCHEMA + 
            NOTIFICATIONS_SCHEMA
        )
        
        try:
            cursor.executescript(master_schema)
        except Exception as e:
            logger.error("Failed to initialize master schema: %s", e)
            raise
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        return create_connection()