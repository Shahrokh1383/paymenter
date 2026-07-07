from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from decimal import Decimal

# Ledger Application Commands & Queries
from src.ledger.application.commands.create_currency_command import CreateCurrencyCommand
from src.ledger.application.commands.toggle_currency_command import ToggleCurrencyCommand
from src.ledger.application.commands.create_account_command import CreateAccountCommand
from src.ledger.application.commands.topup_account_command import TopupAccountCommand
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand
from src.ledger.application.queries.get_all_accounts_query import GetAllAccountsQuery
from src.ledger.application.queries.get_all_escrow_accounts_query import GetAllEscrowAccountsQuery
from src.ledger.application.queries.get_all_currencies_query import GetAllCurrenciesQuery
from src.ledger.application.queries.get_active_currencies_query import GetActiveCurrenciesQuery

# Identity Application Commands & Queries
from src.identity.application.commands.identity_commands import OnboardMerchantCommand, ToggleMerchantCommand
from src.identity.application.commands.register_user_command import RegisterUserCommand
from src.identity.application.queries.identity_queries import GetAllUsersQuery, SearchUsersQuery, GetAllMerchantsQuery

# UoW (Transaction Boundary)
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/currencies', methods=['GET'])
def currencies():
    uow = SqliteUnitOfWork()
    with uow:
        handler = current_app.di_container.get_all_currencies_handler(uow)
        currencies_list = handler.handle(GetAllCurrenciesQuery())
    return render_template('currencies.html', currencies=currencies_list)

@dashboard_bp.route('/currencies/add', methods=['POST'])
def add_currency():
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_create_currency_handler(uow)
            handler.handle(CreateCurrencyCommand(name=request.form['name'], code=request.form['code']))
            current_app.di_container.event_bus.flush()
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.currencies'))

@dashboard_bp.route('/currencies/toggle/<int:id>', methods=['POST'])
def toggle_currency(id):
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_toggle_currency_handler(uow)
            handler.handle(ToggleCurrencyCommand(currency_id=id))
            current_app.di_container.event_bus.flush()
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.currencies'))

@dashboard_bp.route('/users', methods=['GET'])
def users():
    query = request.args.get('query', '')
    uow = SqliteUnitOfWork()
    with uow:
        active_currencies = current_app.di_container.get_active_currencies_handler(uow).handle(GetActiveCurrenciesQuery())
        if query:
            users_list = current_app.di_container.get_search_users_handler(uow).handle(SearchUsersQuery(query))
        else:
            users_list = current_app.di_container.get_all_users_handler(uow).handle(GetAllUsersQuery())
    return render_template('users.html', users=users_list, query=query, currencies=active_currencies)

@dashboard_bp.route('/users/add', methods=['POST'])
def add_user():
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_register_user_handler(uow)
            handler.handle(RegisterUserCommand(name=request.form['name'], phone_email=request.form['phone_email']))
            current_app.di_container.event_bus.flush()
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.users'))

@dashboard_bp.route('/accounts', methods=['GET'])
def accounts():
    uow = SqliteUnitOfWork()
    with uow:
        accounts_list = current_app.di_container.get_all_accounts_handler(uow).handle(GetAllAccountsQuery())
        active_currencies = current_app.di_container.get_active_currencies_handler(uow).handle(GetActiveCurrenciesQuery())
        users_list = current_app.di_container.get_all_users_handler(uow).handle(GetAllUsersQuery())
        merchants_list = current_app.di_container.get_all_merchants_handler(uow).handle(GetAllMerchantsQuery())
    return render_template('accounts.html', accounts=accounts_list, currencies=active_currencies, users=users_list, merchants=merchants_list)

@dashboard_bp.route('/accounts/create', methods=['POST'])
def create_account():
    try:
        owner_id_str = request.form['owner_id']
        currency_code = request.form['currency_code']
        
        owner_type, owner_id = owner_id_str.split('_')
        user_id = int(owner_id) if owner_type == 'user' else None
        merchant_id = int(owner_id) if owner_type == 'merchant' else None

        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_create_account_handler(uow)
            account_id = handler.handle(CreateAccountCommand(user_id=user_id, merchant_id=merchant_id, currency_code=currency_code))
            current_app.di_container.event_bus.flush()
        flash(f"Account created with ID {account_id}.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.accounts'))

@dashboard_bp.route('/accounts/update-currency', methods=['POST'])
def update_account_currency():
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_update_account_currency_handler(uow)
            handler.handle(UpdateAccountCurrencyCommand(account_id=int(request.form['account_id']), currency_code=request.form['currency_code']))
        flash("Account currency updated successfully.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.accounts'))

@dashboard_bp.route('/accounts/topup', methods=['POST'])
def topup_account():
    try:
        amount = Decimal(str(request.form['amount']))
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_topup_account_handler(uow)
            handler.handle(TopupAccountCommand(account_id=int(request.form['account_id']), amount=amount))
            current_app.di_container.event_bus.flush()
        flash("Topup successful.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(request.referrer or url_for('dashboard.accounts'))

@dashboard_bp.route('/escrow', methods=['GET'])
def escrow_accounts():
    uow = SqliteUnitOfWork()
    with uow:
        handler = current_app.di_container.get_all_escrow_accounts_handler(uow)
        escrow_list = handler.handle(GetAllEscrowAccountsQuery())
    return render_template('escrow_accounts.html', accounts=escrow_list)

@dashboard_bp.route('/merchants', methods=['GET'])
def merchants():
    uow = SqliteUnitOfWork()
    with uow:
        merchants_list = current_app.di_container.get_all_merchants_handler(uow).handle(GetAllMerchantsQuery())
    return render_template('merchants.html', merchants=merchants_list)

@dashboard_bp.route('/merchants/add', methods=['POST'])
def add_merchant():
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_onboard_merchant_handler(uow)
            handler.handle(OnboardMerchantCommand(name=request.form['name']))
            current_app.di_container.event_bus.flush()
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.merchants'))

@dashboard_bp.route('/merchants/toggle/<int:id>', methods=['POST'])
def toggle_merchant(id):
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_toggle_merchant_handler(uow)
            handler.handle(ToggleMerchantCommand(merchant_id=id))
            current_app.di_container.event_bus.flush()
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.merchants'))