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
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # Aggregate and execute all schemas atomically
        master_schema = IDENTITY_SCHEMA + LEDGER_SCHEMA + CHECKOUT_SCHEMA + EVENTING_SCHEMA
        cursor.executescript(master_schema)
        
        # Seed default currency
        cursor.execute("SELECT COUNT(*) FROM currencies")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO currencies (name, code, is_active) VALUES (?, ?, ?)", ('Toman', 'IRR', 1))
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn