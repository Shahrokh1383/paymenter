from flask import Blueprint, request, jsonify, g, url_for
from database.connection import get_db_connection
from repositories import merchant_repo
from services import api_service

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.before_request
def authenticate():
    api_key = request.headers.get('x-api-key')
    if not api_key: return jsonify({"error": "Missing x-api-key header"}), 401

    conn = get_db_connection()
    merchant = merchant_repo.get_by_api_key(conn, api_key)
    conn.close()

    if not merchant or not merchant['is_active']: return jsonify({"error": "Invalid or inactive API key"}), 401
    g.merchant = merchant

@api_bp.route('/pay', methods=['POST'])
def pay():
    data = request.get_json()
    if not data or not all(k in data for k in ('amount', 'currency_code', 'user_email', 'callback_url')):
        return jsonify({"error": "Missing required fields: amount, currency_code, user_email, callback_url"}), 400

    try:
        token = api_service.initiate_payment(
            merchant=g.merchant, amount=float(data['amount']), currency_code=data['currency_code'],
            user_email=data['user_email'], callback_url=data['callback_url']
        )
        payment_url = url_for('gateway.show_gateway_page', token=token, _external=True)
        return jsonify({"token": token, "payment_url": payment_url, "status": "Awaiting User Authorization"}), 200
    except api_service.PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@api_bp.route('/refund', methods=['POST'])
def refund():
    data = request.get_json()
    if not data or 'transaction_id' not in data: return jsonify({"error": "Missing transaction_id"}), 400
    try:
        api_service.refund_transaction(merchant=g.merchant, transaction_id=int(data['transaction_id']))
        return jsonify({"transaction_id": data['transaction_id'], "status": "Refunded/Failed"}), 200
    except api_service.PaymentError as e:
        return jsonify({"error": str(e)}), 400

@api_bp.route('/verify/<int:transaction_id>', methods=['GET'])
def verify(transaction_id):
    try:
        txn = api_service.verify_transaction(merchant=g.merchant, transaction_id=transaction_id)
        return jsonify({"transaction_id": txn['id'], "amount": txn['amount'], "currency_code": txn['currency_code'], "status": txn['status']}), 200
    except api_service.PaymentError as e:
        return jsonify({"error": str(e)}), 404