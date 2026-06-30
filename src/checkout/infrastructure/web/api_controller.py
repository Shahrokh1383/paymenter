from flask import Blueprint, request, jsonify, g, url_for
from decimal import Decimal

from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from flask import current_app
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.infrastructure.persistence.sqlite_merchant_repository import SqliteMerchantRepository

from src.checkout.application.commands.initiate_payment_command import InitiatePaymentCommand
from src.checkout.application.commands.refund_payment_command import RefundPaymentCommand
from src.checkout.application.handlers.refund_payment_handler import RefundPaymentHandler

from src.checkout.infrastructure.persistence.ledger_refund_adapter import LedgerRefundAdapter
from src.checkout.infrastructure.persistence.ledger_verification_adapter import LedgerVerificationAdapter
from src.common.domain.exceptions import DomainException

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.before_request
def authenticate():
    """Middleware to authenticate merchant API requests."""
    api_key_raw = request.headers.get('x-api-key')
    if not api_key_raw:
        return jsonify({"error": "Missing x-api-key header"}), 401

    try:
        api_key_vo = ApiKey(api_key_raw)
        uow = SqliteUnitOfWork()
        with uow:
            merchant_repo = SqliteMerchantRepository(uow)
            merchant = merchant_repo.get_by_api_key(api_key_vo)
            
        if not merchant or not merchant.is_active:
            return jsonify({"error": "Invalid or inactive API key"}), 401
            
        g.merchant = merchant
    except ValueError:
        return jsonify({"error": "Invalid API key format"}), 401

@api_bp.route('/pay', methods=['POST'])
def pay():
    """Initiates a new payment session."""
    data = request.get_json()
    if not data or not all(k in data for k in ('amount', 'currency_code', 'user_email', 'callback_url')):
        return jsonify({"error": "Missing required fields: amount, currency_code, user_email, callback_url"}), 400

    try:
        uow = SqliteUnitOfWork()
        event_bus = current_app.di_container.event_bus
        
        command = InitiatePaymentCommand(
            merchant_id=g.merchant.id,
            merchant_name=g.merchant.name,
            amount=Decimal(str(data['amount'])),
            currency_code=data['currency_code'],
            user_email=data['user_email'],
            callback_url=data['callback_url']
        )
        
        with uow:
            handler = current_app.di_container.get_initiate_payment_handler(uow)
            
            token = handler.handle(command)
        
        payment_url = url_for('gateway.show_gateway_page', token=token, _external=True)
        
        return jsonify({
            "token": token,
            "payment_url": payment_url,
            "status": "Awaiting User Authorization"
        }), 200
        
    except DomainException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@api_bp.route('/refund', methods=['POST'])
def refund():
    """Refunds or fails a transaction."""
    data = request.get_json()
    if not data or 'transaction_id' not in data:
        return jsonify({"error": "Missing transaction_id"}), 400
        
    try:
        uow = SqliteUnitOfWork()
        event_bus = current_app.di_container.event_bus
        
        command = RefundPaymentCommand(transaction_id=int(data['transaction_id']))
        
        with uow:
            handler = current_app.di_container.get_refund_payment_handler(uow)
            
            handler.handle(command)
        
        return jsonify({
            "transaction_id": data['transaction_id'],
            "status": "Refunded/Failed"
        }), 200
        
    except DomainException as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@api_bp.route('/verify/<int:transaction_id>', methods=['GET'])
def verify(transaction_id):
    """Verifies the status of a transaction."""
    try:
        uow = SqliteUnitOfWork()
        
        with uow:
            verification_port = LedgerVerificationAdapter(uow)
            status = verification_port.get_transaction_status(transaction_id)
        
        if not status:
            return jsonify({"error": "Transaction not found"}), 404
            
        return jsonify({
            "transaction_id": status.transaction_id,
            "amount": status.amount,
            "currency_code": status.currency_code,
            "status": status.status
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500