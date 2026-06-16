from database.connection import get_db_connection
from repositories import currency_repo, gateway_repo
from services import email_service
from utils.generators import generate_gateway_token, generate_otp_code
from services.ledger import InvalidTransactionStateError
from repositories import transaction_repo

class PaymentError(Exception): pass

def initiate_payment(merchant, amount, currency_code, user_email, callback_url):
    conn = get_db_connection()
    try:
        currency = currency_repo.get_by_code(conn, currency_code)
        if not currency or not currency['is_active']:
            raise PaymentError("Invalid or inactive currency code.")

        token = generate_gateway_token(lambda x: gateway_repo.exists_by_token(conn, x))
        otp = generate_otp_code()

        gateway_repo.insert(
            conn=conn, token=token, merchant_id=merchant['id'], amount=amount,
            currency_id=currency['id'], user_email=user_email, callback_url=callback_url, otp_code=otp
        )
        conn.commit()

        email_service.send_otp_email(user_email, otp, merchant['name'], amount, currency['code'])
        return token

    except Exception as e:
        conn.rollback()
        raise PaymentError(str(e))
    finally:
        conn.close()

def refund_transaction(merchant, transaction_id):
    from services.ledger import fail_and_refund
    from database.transaction import transaction as db_tx
    
    with db_tx() as conn:
        txn = transaction_repo.get_by_id_and_merchant(conn, transaction_id, merchant['id'])
        if not txn: raise PaymentError("Transaction not found.")
        
        try:
            # We need to run fail_and_refund outside the standard context if it manages its own, 
            # but since fail_and_refund uses its own context manager, we just call it.
            pass
        except Exception: pass

    # Execute outside the read-only conn context
    try:
        txn_details = fail_and_refund(transaction_id)
        if txn_details.get('user_email'):
            email_service.send_receipt_email(
                txn_details['user_email'], txn_details['status'], 
                txn_details['amount'], txn_details['currency_code'], merchant['name']
            )
    except InvalidTransactionStateError as e:
        raise PaymentError(str(e))

def verify_transaction(merchant, transaction_id):
    conn = get_db_connection()
    try:
        txn = transaction_repo.get_by_id_and_merchant(conn, transaction_id, merchant['id'])
        if not txn: raise PaymentError("Transaction not found.")
        return txn
    finally:
        conn.close()