from flask import Blueprint, render_template, request, redirect, flash, url_for
from services import gateway_service
from services.gateway_service import GatewayError

gateway_bp = Blueprint('gateway', __name__, url_prefix='/gateway')

@gateway_bp.route('/<token>', methods=['GET'])
def show_gateway_page(token):
    try:
        session = gateway_service.get_session(token)
        return render_template('gateway.html', session=session)
    except GatewayError as e:
        return render_template('gateway_error.html', error_message=str(e))

@gateway_bp.route('/authorize', methods=['POST'])
def authorize():
    token = request.form.get('token')
    card_number = request.form.get('card_number')
    otp_input = request.form.get('otp_code')

    if not all([token, card_number, otp_input]):
        flash("All fields are required.", 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))

    try:
        result = gateway_service.authorize_session(token, card_number, otp_input)
        callback_url = result['callback_url']
        separator = '&' if '?' in callback_url else '?'
        final_url = f"{callback_url}{separator}transaction_id={result['transaction_id']}&gateway_status=Pending"
        return redirect(final_url)
    except GatewayError as e:
        flash(str(e), 'error')
        return redirect(url_for('gateway.show_gateway_page', token=token))