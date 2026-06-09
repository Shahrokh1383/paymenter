from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from services import transaction_service
from services.ledger import hold_funds, complete_funds, fail_and_refund
from services.ledger import InsufficientFundsError, InvalidTransactionStateError, AccountNotFoundError, CurrencyMismatchError

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
        complete_funds(id)
        return jsonify({"success": True, "new_status": "Success"}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Server Error"}), 500

@transaction_bp.route('/fail/<int:id>', methods=['POST'])
def fail(id):
    try:
        fail_and_refund(id)
        return jsonify({"success": True, "new_status": "Failed"}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Server Error"}), 500