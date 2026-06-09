from flask import Blueprint, render_template, request, redirect, url_for, flash
from services import currency_service, user_service, account_service, merchant_service

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# --- Currencies ---
@dashboard_bp.route('/currencies', methods=['GET'])
def currencies():
    currencies_list = currency_service.get_all()
    return render_template('currencies.html', currencies=currencies_list)

@dashboard_bp.route('/currencies/add', methods=['POST'])
def add_currency():
    try:
        currency_service.add(request.form['name'], request.form['code'])
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.currencies'))

@dashboard_bp.route('/currencies/toggle/<int:id>/<int:is_active>', methods=['POST'])
def toggle_currency(id, is_active):
    currency_service.toggle(id, is_active)
    return redirect(url_for('dashboard.currencies'))

# --- Users ---
@dashboard_bp.route('/users', methods=['GET'])
def users():
    query = request.args.get('query', '')
    active_currencies = account_service.get_active_currencies() # Fetch for the dropdown
    if query:
        users_list = user_service.search(query)
    else:
        users_list = user_service.get_all()
    return render_template('users.html', users=users_list, query=query, currencies=active_currencies)

@dashboard_bp.route('/users/add', methods=['POST'])
def add_user():
    try:
        user_service.add(request.form['name'], request.form['phone_email'])
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.users'))

# --- Accounts ---
@dashboard_bp.route('/accounts', methods=['GET'])
def accounts():
    accounts_list = account_service.get_all()
    active_currencies = account_service.get_active_currencies()
    return render_template('accounts.html', accounts=accounts_list, currencies=active_currencies)

@dashboard_bp.route('/accounts/update-currency', methods=['POST'])
def update_account_currency():
    try:
        account_service.update_currency(request.form['account_id'], request.form['currency_id'])
        flash("Account currency updated successfully.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.accounts'))

@dashboard_bp.route('/accounts/topup', methods=['POST'])
def topup_account():
    try:
        account_service.topup(request.form['account_id'], float(request.form['amount']))
        flash("Topup successful.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(request.referrer or url_for('dashboard.accounts')) # Redirect back to previous page

# --- Merchants ---
@dashboard_bp.route('/merchants', methods=['GET'])
def merchants():
    merchants_list = merchant_service.get_all()
    return render_template('merchants.html', merchants=merchants_list)

@dashboard_bp.route('/merchants/add', methods=['POST'])
def add_merchant():
    try:
        merchant_service.add(request.form['name'])
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.merchants'))

@dashboard_bp.route('/merchants/toggle/<int:id>/<int:is_active>', methods=['POST'])
def toggle_merchant(id, is_active):
    merchant_service.toggle(id, is_active)
    return redirect(url_for('dashboard.merchants'))