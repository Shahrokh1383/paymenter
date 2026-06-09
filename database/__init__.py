from .connection import get_db_connection
from .schema import create_tables
from .seed import seed_data

def init_db():
    """Initializes the database: creates tables and seeds data."""
    conn = get_db_connection()
    try:
        create_tables(conn)
        seed_data(conn)
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        conn.close()