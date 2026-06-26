from flask import Blueprint, render_template, request, redirect, flash, url_for

from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.entities.payment_session import PaymentSessionStateError, InvalidOtpError
from src.common.domain.exceptions import DomainException

from src.checkout.application.commands.authorize_payment_command import AuthorizePaymentCommand
from src.checkout.application.handlers.authorize_payment_handler import AuthorizePaymentHandler

from src.checkout.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from src.checkout.infrastructure.persistence.ledger_account_lookup_adapter import LedgerAccountLookupAdapter
from src.checkout.infrastructure.persistence.ledger_fund_reservation_adapter import LedgerFundReservationAdapter

gateway_bp = Blueprint('gateway', __name__, url_prefix='/gateway')

@gateway_bp.route('/<token>', methods=['GET'])
def show_gateway_page(token):
    """Displays the payment gateway page for a given session token."""
    try:
        uow = SqliteUnitOfWork()
        with uow:
            repo = SqliteSessionRepository(uow)
            session = repo.get_by_token(SessionToken(token))
            
            # Prepare view model for template
            session_data = {
                'token': session.token.value,
                'merchant_name': session.merchant_name,
                'amount': float(session.amount.amount),
                'currency_code': session.amount.currency,
                'user_email': session.user_email.value,
                'status': session.status
            }
        return render_template('gateway.html', session=session_data)
    except (ValueError, PaymentSessionStateError) as e:
        return render_template('gateway_error.html', error_message=str(e))

@gateway_bp.route('/authorize', methods=['POST'])
def authorize():
    """Handles the user's authorization attempt (card + OTP)."""
    token = request.form.get('token')
    card_number = request.form.get('card_number')
    otp_input = request.form.get('otp_code')

    if not all([token, card_number, otp_input]):
        flash("All fields are required.", 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))

    try:
        uow = SqliteUnitOfWork()
        command = AuthorizePaymentCommand(
            session_token=token,
            card_number=card_number,
            otp_input=otp_input
        )
        
        handler = AuthorizePaymentHandler(
            uow=uow,
            session_repo=SqliteSessionRepository(uow),
            fund_port=LedgerFundReservationAdapter(uow),
            lookup_port=LedgerAccountLookupAdapter(uow)
        )
        
        transaction_id, callback_url = handler.handle(command)
        
        # Redirect to merchant's callback URL with transaction details
        separator = '&' if '?' in callback_url else '?'
        final_url = f"{callback_url}{separator}transaction_id={transaction_id}&gateway_status=Pending"
        return redirect(final_url)
        
    except (DomainException, InvalidOtpError, PaymentSessionStateError) as e:
        flash(str(e), 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))
    except Exception as e:
        flash(f"Authorization failed: {str(e)}", 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))