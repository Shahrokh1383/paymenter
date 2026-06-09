from database.connection import get_db_connection

def get_all(status=None):
    conn = get_db_connection()
    sql = """
        SELECT t.id, t.amount, t.status, t.created_at,
               from_acc.account_number as from_account,
               to_acc.account_number as to_account,
               c.code as currency_code
        FROM transactions t
        LEFT JOIN accounts from_acc ON t.from_account_id = from_acc.id
        LEFT JOIN accounts to_acc ON t.to_account_id = to_acc.id
        LEFT JOIN currencies c ON t.currency_id = c.id
    """
    params = []
    if status:
        sql += " WHERE t.status = ?"
        params.append(status)
    
    sql += " ORDER BY t.created_at DESC"
    transactions = conn.execute(sql, params).fetchall()
    conn.close()
    return transactions