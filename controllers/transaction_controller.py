from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from services import transaction_service
from services.ledger import hold_funds, complete_funds, fail_and_refund
from services.ledger import InsufficientFundsError, InvalidTransactionStateError, AccountNotFoundError, CurrencyMismatchError
from services import email_service
from database.connection import get_db_connection
from repositories import merchant_repo

transaction_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

@transaction_bp.route('/', methods=['GET'])
def index():
    status_filter = request.args.get('status', '')
    transactions = transaction_service.get_transactions(status_filter if status_filter else None)
    return render_template('transactions.html', transactions=transactions, current_filter=status_filter)

@transaction_bp.route('/create', methods=['POST'])
def create():
    try:
        hold_funds(
            from_account_id=int(request.form['from_account_id']),
            to_account_id=int(request.form['to_account_id']),
            amount=float(request.form['amount']),
            merchant_id=None 
        )
    except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError) as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    return redirect(url_for('transactions.index'))

@transaction_bp.route('/complete/<int:id>', methods=['POST'])
def complete(id):
    try:
        txn_details = complete_funds(id)
        conn = get_db_connection()
        merchant = merchant_repo.get_by_id(conn, txn_details['merchant_id']) if txn_details['merchant_id'] else None
        conn.close()
        merchant_name = merchant['name'] if merchant else "Manual Transfer"
        
        if txn_details.get('user_email'):
            email_service.send_receipt_email(
                to_email=txn_details['user_email'], status="Success", amount=txn_details['amount'],
                currency_code=txn_details['currency_code'], merchant_name=merchant_name
            )
        return jsonify({"success": True, "new_status": "Success"}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400

@transaction_bp.route('/fail/<int:id>', methods=['POST'])
def fail(id):
    try:
        txn_details = fail_and_refund(id)
        conn = get_db_connection()
        merchant = merchant_repo.get_by_id(conn, txn_details['merchant_id']) if txn_details['merchant_id'] else None
        conn.close()
        merchant_name = merchant['name'] if merchant else "Manual Transfer"
        
        if txn_details.get('user_email'):
            email_service.send_receipt_email(
                to_email=txn_details['user_email'], status=txn_details['status'], amount=txn_details['amount'],
                currency_code=txn_details['currency_code'], merchant_name=merchant_name
            )
        return jsonify({"success": True, "new_status": txn_details['status']}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400