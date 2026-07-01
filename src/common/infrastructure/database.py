import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), 'storage')
DB_PATH = os.path.join(DB_DIR, 'paymenter.db')

from src.common.infrastructure.database.schemas.identity.identity import IDENTITY_SCHEMA
from src.common.infrastructure.database.schemas.ledger.ledger import LEDGER_SCHEMA
from src.common.infrastructure.database.schemas.checkout.checkout import CHECKOUT_SCHEMA
from src.common.infrastructure.database.schemas.eventing.eventing import EVENTING_SCHEMA

class Database:
    @staticmethod
    def initialize() -> None:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # Aggregate and execute all schemas atomically
        master_schema = IDENTITY_SCHEMA + LEDGER_SCHEMA + CHECKOUT_SCHEMA + EVENTING_SCHEMA
        cursor.executescript(master_schema)
        
        # Seed System User for System/Escrow Account Foreign Key Integrity
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, name, phone_email) 
            VALUES (0, 'System', 'system@paymenter.local')
        """)
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn