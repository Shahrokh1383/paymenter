from database.connection import get_db_connection

def get_all():
    conn = get_db_connection()
    merchants = conn.execute("""
        SELECT m.*, a.balance as settlement_balance 
        FROM merchants m
        LEFT JOIN accounts a ON m.settlement_account_id = a.id
    """).fetchall()
    conn.close()
    return merchants

def get_by_api_key(conn, api_key):
    cursor = conn.execute("SELECT * FROM merchants WHERE api_key = ?", (api_key,))
    return cursor.fetchone()

def insert(conn, name, api_key, settlement_account_id):
    cursor = conn.execute(
        "INSERT INTO merchants (name, api_key, settlement_account_id) VALUES (?, ?, ?)",
        (name, api_key, settlement_account_id)
    )
    return cursor.lastrowid

def toggle(conn, merchant_id, is_active):
    conn.execute("UPDATE merchants SET is_active = ? WHERE id = ?", (not is_active, merchant_id))