from database.connection import get_db_connection

def insert(conn, token, merchant_id, amount, currency_id, user_email, callback_url, otp_code):
    cursor = conn.execute("""
        INSERT INTO gateway_sessions (token, merchant_id, amount, currency_id, user_email, callback_url, otp_code)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (token, merchant_id, amount, currency_id, user_email, callback_url, otp_code))
    return cursor.lastrowid

def get_by_token(conn, token):
    cursor = conn.execute("""
        SELECT gs.*, m.name as merchant_name, c.code as currency_code, c.name as currency_name
        FROM gateway_sessions gs
        JOIN merchants m ON gs.merchant_id = m.id
        JOIN currencies c ON gs.currency_id = c.id
        WHERE gs.token = ?
    """, (token,))
    return cursor.fetchone()

def update_status(conn, token, status, transaction_id=None):
    if transaction_id:
        conn.execute("UPDATE gateway_sessions SET status = ?, transaction_id = ? WHERE token = ?", (status, transaction_id, token))
    else:
        conn.execute("UPDATE gateway_sessions SET status = ? WHERE token = ?", (status, token))

def exists_by_token(conn, token):
    cursor = conn.execute("SELECT id FROM gateway_sessions WHERE token = ?", (token,))
    return cursor.fetchone() is not None