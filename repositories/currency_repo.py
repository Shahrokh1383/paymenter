from database.connection import get_db_connection

def get_all():
    conn = get_db_connection()
    currencies = conn.execute("SELECT * FROM currencies").fetchall()
    conn.close()
    return currencies

def insert(conn, name, code):
    cursor = conn.execute("INSERT INTO currencies (name, code) VALUES (?, ?)", (name, code))
    return cursor.lastrowid

def toggle(conn, currency_id, is_active):
    conn.execute("UPDATE currencies SET is_active = ? WHERE id = ?", (not is_active, currency_id))

def exists_by_code(conn, code):
    cursor = conn.execute("SELECT id FROM currencies WHERE code = ?", (code,))
    return cursor.fetchone() is not None