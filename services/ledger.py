from database.transaction import transaction

# --- Custom Exceptions ---
class InsufficientFundsError(Exception): pass
class AccountNotFoundError(Exception): pass
class CurrencyMismatchError(Exception): pass
class InvalidTransactionStateError(Exception): pass

def hold_funds(from_account_id: int, to_account_id: int, amount: float, merchant_id: int = None) -> int:
    """
    Deducts funds from the source account and creates a Pending transaction.
    Automatically detects currency from the source account.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        # Fetch accounts
        cursor.execute("SELECT id, balance, currency_id FROM accounts WHERE id = ?", (from_account_id,))
        from_acc = cursor.fetchone()
        cursor.execute("SELECT id, balance, currency_id FROM accounts WHERE id = ?", (to_account_id,))
        to_acc = cursor.fetchone()

        # Validations
        if not from_acc or not to_acc:
            raise AccountNotFoundError("One or both accounts do not exist.")

        # Auto-detect currency from the source account
        transaction_currency_id = from_acc['currency_id']

        # ENFORCE CURRENCY MATCH
        if to_acc['currency_id'] != transaction_currency_id:
            raise CurrencyMismatchError("Source and Destination accounts must have the same currency.")

        if from_acc['balance'] < amount:
            raise InsufficientFundsError("Insufficient balance in the source account.")

        # Deduct from sender
        new_from_balance = from_acc['balance'] - amount
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from_balance, from_account_id))

        # Create Pending transaction using the auto-detected currency
        cursor.execute("""
            INSERT INTO transactions (merchant_id, from_account_id, to_account_id, amount, currency_id, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (merchant_id, from_account_id, to_account_id, amount, transaction_currency_id))

        return cursor.lastrowid

# ... (complete_funds and fail_and_refund remain exactly the same as before) ...
def complete_funds(transaction_id: int) -> None:
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, to_account_id, amount, status FROM transactions WHERE id = ?", (transaction_id,))
        txn = cursor.fetchone()
        if not txn: raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] != 'Pending': raise InvalidTransactionStateError(f"Transaction cannot be completed. Current status: {txn['status']}")
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['to_account_id']))
        cursor.execute("UPDATE transactions SET status = 'Success' WHERE id = ?", (transaction_id,))

def fail_and_refund(transaction_id: int) -> None:
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, from_account_id, amount, status FROM transactions WHERE id = ?", (transaction_id,))
        txn = cursor.fetchone()
        if not txn: raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] not in ('Pending', 'Success'): raise InvalidTransactionStateError(f"Transaction cannot be refunded. Current status: {txn['status']}")
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['from_account_id']))
        new_status = 'Failed' if txn['status'] == 'Pending' else 'Refunded'
        cursor.execute("UPDATE transactions SET status = ? WHERE id = ?", (new_status, transaction_id))