from database.connection import get_db_connection

def get_all():
    conn = get_db_connection()
    # Added LEFT JOIN with currencies table to fetch currency_code
    users = conn.execute("""
        SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance, c.code as currency_code
        FROM users u
        LEFT JOIN accounts a ON u.id = a.user_id
        LEFT JOIN currencies c ON a.currency_id = c.id
    """).fetchall()
    conn.close()
    return users

def insert(conn, name, phone_email):
    cursor = conn.execute("INSERT INTO users (name, phone_email) VALUES (?, ?)", (name, phone_email))
    return cursor.lastrowid

def search(conn, query):
    # Added LEFT JOIN with currencies table to fetch currency_code
    sql = """
        SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance, c.code as currency_code
        FROM users u
        LEFT JOIN accounts a ON u.id = a.user_id
        LEFT JOIN currencies c ON a.currency_id = c.id
        WHERE u.name LIKE ? OR a.account_number LIKE ? OR a.card_number LIKE ?
    """
    like_query = f"%{query}%"
    return conn.execute(sql, (like_query, like_query, like_query)).fetchall()