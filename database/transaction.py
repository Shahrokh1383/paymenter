from contextlib import contextmanager
from .connection import get_db_connection

@contextmanager
def transaction():
    """Context manager for database transactions. Commits on success, rolls back on exception."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise  # Re-raise the exception so the caller knows it failed
    finally:
        conn.close()