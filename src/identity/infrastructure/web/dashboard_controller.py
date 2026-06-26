from flask import Blueprint, render_template, request, redirect, url_for, flash
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork

# Identity Imports
from src.identity.application.commands.identity_commands import OnboardMerchantCommand, ToggleMerchantCommand, AddCurrencyCommand, ToggleCurrencyCommand
from src.identity.application.handlers.identity_handlers import OnboardMerchantHandler, ToggleMerchantHandler, AddCurrencyHandler, ToggleCurrencyHandler
from src.identity.application.queries.identity_queries import GetAllUsersQuery, SearchUsersQuery, GetAllMerchantsQuery, GetAllCurrenciesQuery
from src.identity.application.handlers.identity_query_handlers import GetAllUsersHandler, SearchUsersHandler, GetAllMerchantsHandler, GetAllCurrenciesHandler
from src.identity.infrastructure.persistence.sqlite_user_repository import SqliteUserRepository
from src.identity.infrastructure.persistence.sqlite_merchant_repository import SqliteMerchantRepository
from src.identity.infrastructure.persistence.sqlite_currency_repository import SqliteCurrencyRepository
from src.identity.infrastructure.persistence.ledger_account_provisioning_adapter import LedgerAccountProvisioningAdapter
from src.identity.application.commands.register_user_command import RegisterUserCommand
from src.identity.application.handlers.register_user_handler import RegisterUserHandler

# Ledger Imports
from src.ledger.application.commands.topup_account_command import TopupAccountCommand
from src.ledger.application.handlers.topup_account_handler import TopupAccountHandler
from src.ledger.application.commands.update_account_currency_command import UpdateAccountCurrencyCommand
from src.ledger.application.handlers.update_account_currency_handler import UpdateAccountCurrencyHandler
from src.ledger.application.queries.get_all_accounts_query import GetAllAccountsQuery
from src.ledger.application.handlers.get_all_accounts_handler import GetAllAccountsHandler
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_account_read_model import SqliteAccountReadModel

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# --- Currencies ---
@dashboard_bp.route('/currencies', methods=['GET'])
def currencies():
    uow = SqliteUnitOfWork()
    with uow:
        handler = GetAllCurrenciesHandler(SqliteCurrencyRepository(uow))
        currencies_list = handler.handle(GetAllCurrenciesQuery())
    return render_template('currencies.html', currencies=currencies_list)

@dashboard_bp.route('/currencies/add', methods=['POST'])
def add_currency():
    try:
        uow = SqliteUnitOfWork()
        handler = AddCurrencyHandler(uow, SqliteCurrencyRepository(uow))
        handler.handle(AddCurrencyCommand(name=request.form['name'], code=request.form['code']))
    except Exception as e: flash(str(e), 'error')
    return redirect(url_for('dashboard.currencies'))

@dashboard_bp.route('/currencies/toggle/<int:id>/<int:is_active>', methods=['POST'])
def toggle_currency(id, is_active):
    uow = SqliteUnitOfWork()
    handler = ToggleCurrencyHandler(uow, SqliteCurrencyRepository(uow))
    handler.handle(ToggleCurrencyCommand(currency_id=id))
    return redirect(url_for('dashboard.currencies'))

# --- Users ---
@dashboard_bp.route('/users', methods=['GET'])
def users():
    query = request.args.get('query', '')
    uow = SqliteUnitOfWork()
    with uow:
        active_currencies = SqliteCurrencyRepository(uow).get_active()
        if query:
            users_list = SearchUsersHandler(SqliteUserRepository(uow)).handle(SearchUsersQuery(query))
        else:
            users_list = GetAllUsersHandler(SqliteUserRepository(uow)).handle(GetAllUsersQuery())
    return render_template('users.html', users=users_list, query=query, currencies=active_currencies)

@dashboard_bp.route('/users/add', methods=['POST'])
def add_user():
    try:
        uow = SqliteUnitOfWork()
        handler = RegisterUserHandler(uow, SqliteUserRepository(uow), LedgerAccountProvisioningAdapter(uow))
        handler.handle(RegisterUserCommand(name=request.form['name'], phone_email=request.form['phone_email']))
    except Exception as e: flash(str(e), 'error')
    return redirect(url_for('dashboard.users'))

# --- Accounts ---
@dashboard_bp.route('/accounts', methods=['GET'])
def accounts():
    uow = SqliteUnitOfWork()
    with uow:
        accounts_list = GetAllAccountsHandler(SqliteAccountReadModel(uow)).handle(GetAllAccountsQuery())
        active_currencies = SqliteCurrencyRepository(uow).get_active()
    return render_template('accounts.html', accounts=accounts_list, currencies=active_currencies)

@dashboard_bp.route('/accounts/update-currency', methods=['POST'])
def update_account_currency():
    try:
        uow = SqliteUnitOfWork()
        handler = UpdateAccountCurrencyHandler(uow, SqliteAccountRepository(uow))
        handler.handle(UpdateAccountCurrencyCommand(account_id=int(request.form['account_id']), currency_id=int(request.form['currency_id'])))
        flash("Account currency updated successfully.", 'success')
    except Exception as e: flash(str(e), 'error')
    return redirect(url_for('dashboard.accounts'))

@dashboard_bp.route('/accounts/topup', methods=['POST'])
def topup_account():
    try:
        uow = SqliteUnitOfWork()
        handler = TopupAccountHandler(uow, SqliteAccountRepository(uow))
        handler.handle(TopupAccountCommand(account_id=int(request.form['account_id']), amount=float(request.form['amount'])))
        flash("Topup successful.", 'success')
    except Exception as e: flash(str(e), 'error')
    return redirect(request.referrer or url_for('dashboard.accounts'))

# --- Merchants ---
@dashboard_bp.route('/merchants', methods=['GET'])
def merchants():
    uow = SqliteUnitOfWork()
    with uow:
        merchants_list = GetAllMerchantsHandler(SqliteMerchantRepository(uow)).handle(GetAllMerchantsQuery())
    return render_template('merchants.html', merchants=merchants_list)

@dashboard_bp.route('/merchants/add', methods=['POST'])
def add_merchant():
    try:
        uow = SqliteUnitOfWork()
        handler = OnboardMerchantHandler(uow, SqliteUserRepository(uow), SqliteMerchantRepository(uow), LedgerAccountProvisioningAdapter(uow))
        handler.handle(OnboardMerchantCommand(name=request.form['name']))
    except Exception as e: flash(str(e), 'error')
    return redirect(url_for('dashboard.merchants'))

@dashboard_bp.route('/merchants/toggle/<int:id>/<int:is_active>', methods=['POST'])
def toggle_merchant(id, is_active):
    uow = SqliteUnitOfWork()
    handler = ToggleMerchantHandler(uow, SqliteMerchantRepository(uow))
    handler.handle(ToggleMerchantCommand(merchant_id=id))
    return redirect(url_for('dashboard.merchants'))