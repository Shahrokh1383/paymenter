import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), 'storage')
DB_PATH = os.path.join(DB_DIR, 'paymenter.db')

class Database:
    @staticmethod
    def initialize() -> None:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS currencies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone_email TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS merchants (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, api_key TEXT NOT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT 1, settlement_account_id INTEGER, FOREIGN KEY (settlement_account_id) REFERENCES accounts(id));
            CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, currency_id INTEGER NOT NULL, account_number TEXT NOT NULL UNIQUE, card_number TEXT NOT NULL UNIQUE, balance REAL NOT NULL DEFAULT 0.0, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (currency_id) REFERENCES currencies(id));
            CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id INTEGER, from_account_id INTEGER NOT NULL, to_account_id INTEGER NOT NULL, amount REAL NOT NULL, currency_id INTEGER NOT NULL, status TEXT NOT NULL, user_email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (merchant_id) REFERENCES merchants(id), FOREIGN KEY (from_account_id) REFERENCES accounts(id), FOREIGN KEY (to_account_id) REFERENCES accounts(id), FOREIGN KEY (currency_id) REFERENCES currencies(id));
            CREATE TABLE IF NOT EXISTS gateway_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, merchant_id INTEGER NOT NULL, amount REAL NOT NULL, currency_id INTEGER NOT NULL, user_email TEXT NOT NULL, callback_url TEXT NOT NULL, otp_code TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Initiated', transaction_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (merchant_id) REFERENCES merchants(id), FOREIGN KEY (currency_id) REFERENCES currencies(id), FOREIGN KEY (transaction_id) REFERENCES transactions(id));
        """)
        
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