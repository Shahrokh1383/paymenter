from flask import Blueprint, jsonify, current_app
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.common.infrastructure.web.idempotency import idempotent
from src.common.domain.exceptions import (
    InsufficientFundsError, AccountNotFoundError, 
    CurrencyMismatchError, InvalidTransactionStateError
)

from src.ledger.application.commands.complete_funds_command import CompleteFundsCommand
from src.ledger.application.commands.fail_and_refund_command import FailAndRefundCommand

transaction_api_bp = Blueprint('transactions_api', __name__, url_prefix='/api/transactions')

@transaction_api_bp.route('/<int:id>/complete', methods=['POST'])
@idempotent
def complete(id):
    try:
        command = CompleteFundsCommand(transaction_id=id)
        uow = SqliteUnitOfWork()
        handler = current_app.di_container.get_complete_funds_handler(uow)
        handler.handle(command)
        
        return jsonify({"success": True, "new_status": "Success"}), 200
        
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError) as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        # Bug 3 & Info Leakage Fix: Log internally, hide from client
        current_app.logger.error(f"Unexpected error completing transaction {id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500

@transaction_api_bp.route('/<int:id>/fail', methods=['POST'])
@idempotent
def fail(id):
    try:
        command = FailAndRefundCommand(transaction_id=id)
        uow = SqliteUnitOfWork()
        handler = current_app.di_container.get_fail_and_refund_handler(uow)
        handler.handle(command)
        
        return jsonify({"success": True, "new_status": "Refunded/Failed"}), 200
        
    except InvalidTransactionStateError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError) as e:
        # Bug 1 Fix: Insufficient funds during refund is now a 409 Conflict, not 500
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        # Bug 3 & Info Leakage Fix: Log internally, hide from client
        current_app.logger.error(f"Unexpected error failing transaction {id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500