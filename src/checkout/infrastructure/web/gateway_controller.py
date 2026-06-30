from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.entities.payment_session import PaymentSessionStateError, InvalidOtpError
from src.common.domain.exceptions import DomainException

from src.checkout.application.commands.authorize_payment_command import AuthorizePaymentCommand
from src.checkout.application.commands.request_otp_command import RequestOtpCommand

from src.app.di_container import DIContainer
from src.checkout.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository

gateway_bp = Blueprint('gateway', __name__, url_prefix='/gateway')
container = DIContainer()

@gateway_bp.route('/<token>', methods=['GET'])
def show_gateway_page(token):
    try:
        uow = SqliteUnitOfWork()
        with uow:
            repo = SqliteSessionRepository(uow)
            session = repo.get_by_token(SessionToken(token))
            
            session_data = {
                'token': session.token.value,
                'merchant_name': session.merchant_name,
                'amount': float(session.amount.amount),
                'currency_code': session.amount.currency,
                'user_email': session.user_email.value,
                'status': session.status,
                'otp_requested': session.otp_code is not None
            }
        return render_template('gateway.html', session=session_data)
    except (ValueError, PaymentSessionStateError) as e:
        return render_template('gateway_error.html', error_message=str(e))

@gateway_bp.route('/request-otp', methods=['POST'])
def request_otp():
    """AJAX endpoint to request OTP for a specific card."""
    data = request.get_json()
    token = data.get('token')
    card_number = data.get('card_number')

    if not token or not card_number:
        return jsonify({"error": "Token and Card Number are required."}), 400

    try:
        uow = SqliteUnitOfWork()
        command = RequestOtpCommand(session_token=token, card_number=card_number)
        handler = container.get_request_otp_handler(uow)
        
        result = handler.handle(command)
        return jsonify({"success": True, "expires_in": result["expires_in_seconds"]}), 200
        
    except (DomainException, PaymentSessionStateError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to request OTP: {str(e)}"}), 500

@gateway_bp.route('/authorize', methods=['POST'])
def authorize():
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
        
        handler = container.get_authorize_payment_handler(uow)
        transaction_id, callback_url = handler.handle(command)
        
        separator = '&' if '?' in callback_url else '?'
        final_url = f"{callback_url}{separator}transaction_id={transaction_id}&gateway_status=Pending"
        return redirect(final_url)
        
    except (DomainException, InvalidOtpError, PaymentSessionStateError) as e:
        flash(str(e), 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))
    except Exception as e:
        flash(f"Authorization failed: {str(e)}", 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))