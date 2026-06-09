import sqlite3
import os

# Dynamically resolve the path to the database file inside the storage folder
DB_DIR = os.path.join(os.path.dirname(__file__), 'storage')
DB_PATH = os.path.join(DB_DIR, 'paymenter.db')

def get_db_connection():
    """Creates and returns a database connection with foreign keys enforced."""
    # Ensure the storage directory exists
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON;")  # Enforce relational integrity
    return conn