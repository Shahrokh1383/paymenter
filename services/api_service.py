from database.connection import get_db_connection
from database.transaction import transaction
from repositories import account_repo, currency_repo, transaction_repo
from services.ledger import hold_funds, fail_and_refund
from services.ledger import InsufficientFundsError, InvalidTransactionStateError

class PaymentError(Exception): pass

def initiate_payment(merchant, destination_card_number, amount, currency_code):
    conn = get_db_connection()
    try:
        # 1. Validate Currency
        currency = currency_repo.get_by_code(conn, currency_code)
        if not currency or not currency['is_active']:
            raise PaymentError("Invalid or inactive currency code.")

        # 2. Find User Account by Card Number
        user_account = account_repo.get_by_card_number(conn, destination_card_number)
        if not user_account:
            raise PaymentError("Destination card number not found.")

        # 3. Validate User Account Currency matches requested currency
        if user_account['currency_id'] != currency['id']:
            raise PaymentError("Destination card currency does not match the requested currency.")

        # 4. Find Merchant Settlement Account for this currency
        settlement_account = account_repo.get_settlement_account(conn, merchant['id'], currency['id'])
        if not settlement_account:
            raise PaymentError("Merchant does not have a settlement account for this currency.")

        # 5. Execute Hold Funds (User pays Merchant)
        txn_id = hold_funds(
            from_account_id=user_account['id'],
            to_account_id=settlement_account['id'],
            amount=amount,
            merchant_id=merchant['id']
        )
        return txn_id

    except InsufficientFundsError as e:
        raise PaymentError(str(e))
    finally:
        conn.close()

def refund_transaction(merchant, transaction_id):
    with transaction() as conn:
        # Verify ownership
        txn = transaction_repo.get_by_id_and_merchant(conn, transaction_id, merchant['id'])
        if not txn:
            raise PaymentError("Transaction not found or does not belong to this merchant.")
        
        try:
            fail_and_refund(transaction_id)
        except InvalidTransactionStateError as e:
            raise PaymentError(str(e))

def verify_transaction(merchant, transaction_id):
    conn = get_db_connection()
    try:
        txn = transaction_repo.get_by_id_and_merchant(conn, transaction_id, merchant['id'])
        if not txn:
            raise PaymentError("Transaction not found or does not belong to this merchant.")
        return txn
    finally:
        conn.close()