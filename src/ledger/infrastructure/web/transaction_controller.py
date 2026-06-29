from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from src.ledger.infrastructure.web.schemas.hold_funds_request import HoldFundsRequestSchema
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.common.domain.exceptions import (
    InsufficientFundsError, AccountNotFoundError, 
    CurrencyMismatchError
)

from src.ledger.application.commands.hold_funds_command import HoldFundsCommand
from src.ledger.application.queries.get_transactions_query import GetTransactionsQuery

transaction_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

@transaction_bp.route('/', methods=['GET'])
def index():
    status_filter = request.args.get('status', '')
    query = GetTransactionsQuery(status_filter=status_filter if status_filter else None)
    
    uow = SqliteUnitOfWork()
    with uow:
        handler = current_app.di_container.get_transactions_handler(uow)
        transactions = handler.handle(query)
    
    return render_template('transactions.html', transactions=transactions, current_filter=status_filter)

@transaction_bp.route('/create', methods=['POST'])
def create():
    try:
        validated_data = HoldFundsRequestSchema.validate(request.form)
        
        command = HoldFundsCommand(
            from_account_id=validated_data['from_account_id'],
            to_account_id=validated_data['to_account_id'],
            amount=validated_data['amount'],
            merchant_id=validated_data['merchant_id'],
            user_email=validated_data['user_email']
        )
        
        uow = SqliteUnitOfWork()
        handler = current_app.di_container.get_hold_funds_handler(uow)
        handler.handle(command)
        
        flash("Funds held successfully.", "success")
        
    except (InsufficientFundsError, AccountNotFoundError, CurrencyMismatchError) as e:
        flash(str(e), 'error')
    except ValueError as e:
        # Caught from HoldFundsRequestSchema
        flash(str(e), 'error')
    except Exception as e:
        current_app.logger.error(f"Unexpected error creating transaction: {str(e)}", exc_info=True)
        flash("An unexpected system error occurred. Please try again.", 'error')
        
    return redirect(url_for('transactions.index'))