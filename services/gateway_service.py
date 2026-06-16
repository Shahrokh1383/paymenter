from database.connection import get_db_connection
from repositories import gateway_repo, account_repo
from services.ledger import hold_funds, InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError

class GatewayError(Exception): pass

def get_session(token):
    conn = get_db_connection()
    try:
        session = gateway_repo.get_by_token(conn, token)
        if not session: raise GatewayError("Invalid or expired payment session.")
        if session['status'] != 'Initiated': raise GatewayError(f"This payment session is already {session['status']}.")
        return session
    finally:
        conn.close()

def authorize_session(token, card_number, otp_input):
    conn = get_db_connection()
    try:
        session = gateway_repo.get_by_token(conn, token)
        if not session: raise GatewayError("Invalid or expired payment session.")
        if session['status'] != 'Initiated': raise GatewayError(f"This payment session is already {session['status']}.")

        if str(session['otp_code']) != str(otp_input):
            raise GatewayError("Invalid OTP code. Please check your email and try again.")

        user_account = account_repo.get_by_card_number(conn, card_number)
        if not user_account: raise GatewayError("Card number not found in our system.")

        settlement_account = account_repo.get_settlement_account(conn, session['merchant_id'], session['currency_id'])
        if not settlement_account: raise GatewayError("Merchant settlement configuration error.")

        try:
            txn_id = hold_funds(
                from_account_id=user_account['id'], to_account_id=settlement_account['id'],
                amount=session['amount'], merchant_id=session['merchant_id'], user_email=session['user_email']
            )
        except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError) as e:
            raise GatewayError(str(e))

        gateway_repo.update_status(conn, token, 'Authorized', txn_id)
        conn.commit()

        return {"transaction_id": txn_id, "callback_url": session['callback_url']}

    except Exception as e:
        conn.rollback()
        if isinstance(e, GatewayError): raise e
        raise GatewayError(f"Authorization failed: {str(e)}")
    finally:
        conn.close()