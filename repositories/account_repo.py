from database.connection import get_db_connection

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