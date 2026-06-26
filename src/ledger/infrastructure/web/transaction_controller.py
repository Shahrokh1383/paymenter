from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from decimal import Decimal, InvalidOperation

from src.common.domain.exceptions import (
    InsufficientFundsError, AccountNotFoundError, 
    CurrencyMismatchError, InvalidTransactionStateError
)

from src.ledger.application.commands.hold_funds_command import HoldFundsCommand
from src.ledger.application.commands.complete_funds_command import CompleteFundsCommand
from src.ledger.application.commands.fail_and_refund_command import FailAndRefundCommand
from src.ledger.application.queries.get_transactions_query import GetTransactionsQuery

from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler
from src.ledger.application.handlers.complete_funds_handler import CompleteFundsHandler
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.application.handlers.get_transactions_handler import GetTransactionsHandler

from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_read_model import SqliteTransactionReadModel

transaction_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

# --- Temporary DI Factory (Will move to di_container.py in Phase 5) ---
def _get_uow(): return SqliteUnitOfWork()
def _get_account_repo(uow): return SqliteAccountRepository(uow)
def _get_txn_repo(uow): return SqliteTransactionRepository(uow)

@transaction_bp.route('/', methods=['GET'])
def index():
    status_filter = request.args.get('status', '')
    query = GetTransactionsQuery(status_filter=status_filter if status_filter else None)
    
    handler = GetTransactionsHandler(SqliteTransactionReadModel())
    transactions = handler.handle(query)
    
    return render_template('transactions.html', transactions=transactions, current_filter=status_filter)

@transaction_bp.route('/create', methods=['POST'])
def create():
    try:
        amount = Decimal(str(request.form['amount']))
        merchant_id_str = request.form.get('merchant_id')
        merchant_id = int(merchant_id_str) if merchant_id_str else None
        
        command = HoldFundsCommand(
            from_account_id=int(request.form['from_account_id']),
            to_account_id=int(request.form['to_account_id']),
            amount=amount,
            merchant_id=merchant_id,
            user_email=request.form.get('user_email')
        )
        
        uow = _get_uow()
        handler = HoldFundsHandler(uow, _get_account_repo(uow), _get_txn_repo(uow))
        handler.handle(command)
        
        flash("Funds held successfully.", "success")
    except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError, InvalidOperation) as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        
    return redirect(url_for('transactions.index'))

@transaction_bp.route('/complete/<int:id>', methods=['POST'])
def complete(id):
    try:
        command = CompleteFundsCommand(transaction_id=id)
        uow = _get_uow()
        handler = CompleteFundsHandler(uow, _get_account_repo(uow), _get_txn_repo(uow))
        handler.handle(command)
        
        # NOTE: Email dispatch will be handled via EventBus in Phase 4.
        return jsonify({"success": True, "new_status": "Success"}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@transaction_bp.route('/fail/<int:id>', methods=['POST'])
def fail(id):
    try:
        command = FailAndRefundCommand(transaction_id=id)
        uow = _get_uow()
        handler = FailAndRefundHandler(uow, _get_account_repo(uow), _get_txn_repo(uow))
        handler.handle(command)
        
        # NOTE: Email dispatch will be handled via EventBus in Phase 4.
        return jsonify({"success": True, "new_status": "Refunded/Failed"}), 200
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500