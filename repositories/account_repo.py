from database.connection import get_db_connection

def get_all():
    conn = get_db_connection()
    accounts = conn.execute("""
        SELECT a.id, a.user_id, a.currency_id, a.account_number, a.card_number, a.balance,
               u.name as user_name,
               c.code as currency_code
        FROM accounts a
        LEFT JOIN users u ON a.user_id = u.id
        LEFT JOIN currencies c ON a.currency_id = c.id
        ORDER BY a.id
    """).fetchall()
    conn.close()
    return accounts

def update_currency(conn, account_id, currency_id):
    conn.execute("UPDATE accounts SET currency_id = ? WHERE id = ?", (currency_id, account_id))

# ... (Keep existing insert, topup, exists functions)
def insert(conn, user_id, currency_id, account_number, card_number):
    cursor = conn.execute(
        "INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, 0.0)",
        (user_id, currency_id, account_number, card_number)
    )
    return cursor.lastrowid

def topup(conn, account_id, amount):
    conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, account_id))

def exists_by_account_number(conn, account_number):
    cursor = conn.execute("SELECT id FROM accounts WHERE account_number = ?", (account_number,))
    return cursor.fetchone() is not None

def exists_by_card_number(conn, card_number):
    cursor = conn.execute("SELECT id FROM accounts WHERE card_number = ?", (card_number,))
    return cursor.fetchone() is not None