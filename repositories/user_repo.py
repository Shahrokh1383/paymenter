from database.connection import get_db_connection

def get_all():
    conn = get_db_connection()
    # LEFT JOIN ensures we get the user even if they somehow don't have an account yet
    users = conn.execute("""
        SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance
        FROM users u
        LEFT JOIN accounts a ON u.id = a.user_id
    """).fetchall()
    conn.close()
    return users

def insert(conn, name, phone_email):
    cursor = conn.execute("INSERT INTO users (name, phone_email) VALUES (?, ?)", (name, phone_email))
    return cursor.lastrowid

def search(conn, query):
    # Join users and accounts to search across name, account_number, and card_number
    sql = """
        SELECT u.id, u.name, u.phone_email, a.id as account_id, a.account_number, a.card_number, a.balance
        FROM users u
        LEFT JOIN accounts a ON u.id = a.user_id
        WHERE u.name LIKE ? OR a.account_number LIKE ? OR a.card_number LIKE ?
    """
    like_query = f"%{query}%"
    return conn.execute(sql, (like_query, like_query, like_query)).fetchall()