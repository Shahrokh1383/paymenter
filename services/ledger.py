from database.transaction import transaction

# --- Custom Exceptions for Clean Business Logic ---
class InsufficientFundsError(Exception): pass
class AccountNotFoundError(Exception): pass
class CurrencyMismatchError(Exception): pass
class InvalidTransactionStateError(Exception): pass

def hold_funds(from_account_id: int, to_account_id: int, amount: float, currency_id: int, merchant_id: int = None) -> int:
    """
    Deducts funds from the source account and creates a Pending transaction.
    Returns the new transaction ID.
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
        if from_acc['currency_id'] != currency_id or to_acc['currency_id'] != currency_id:
            raise CurrencyMismatchError("Account currencies do not match the transaction currency.")
        if from_acc['balance'] < amount:
            raise InsufficientFundsError("Insufficient balance in the source account.")

        # Deduct from sender
        new_from_balance = from_acc['balance'] - amount
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from_balance, from_account_id))

        # Create Pending transaction
        cursor.execute("""
            INSERT INTO transactions (merchant_id, from_account_id, to_account_id, amount, currency_id, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (merchant_id, from_account_id, to_account_id, amount, currency_id))

        return cursor.lastrowid


def complete_funds(transaction_id: int) -> None:
    """
    Completes a Pending transaction, adding funds to the destination account.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, to_account_id, amount, status FROM transactions WHERE id = ?", (transaction_id,))
        txn = cursor.fetchone()

        if not txn:
            raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] != 'Pending':
            raise InvalidTransactionStateError(f"Transaction cannot be completed. Current status: {txn['status']}")

        # Add to receiver
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['to_account_id']))

        # Update transaction status
        cursor.execute("UPDATE transactions SET status = 'Success' WHERE id = ?", (transaction_id,))


def fail_and_refund(transaction_id: int) -> None:
    """
    Fails/Refunds a transaction, returning funds to the original sender.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, from_account_id, amount, status FROM transactions WHERE id = ?", (transaction_id,))
        txn = cursor.fetchone()

        if not txn:
            raise InvalidTransactionStateError("Transaction not found.")
        if txn['status'] not in ('Pending', 'Success'):
            raise InvalidTransactionStateError(f"Transaction cannot be refunded. Current status: {txn['status']}")

        # Refund to sender
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn['amount'], txn['from_account_id']))

        # Update transaction status
        new_status = 'Failed' if txn['status'] == 'Pending' else 'Refunded'
        cursor.execute("UPDATE transactions SET status = ? WHERE id = ?", (new_status, transaction_id))