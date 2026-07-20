from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.notifications.application.queries.get_all_deliveries_query import GetAllDeliveriesQuery
from src.notifications.application.commands.retry_webhook_delivery_command import RetryWebhookDeliveryCommand

webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

@webhook_bp.route('/', methods=['GET'])
def index():
    uow = SqliteUnitOfWork()
    with uow:
        handler = current_app.di_container.get_all_deliveries_handler(uow)
        deliveries = handler.handle(GetAllDeliveriesQuery())
    return render_template('webhooks.html', deliveries=deliveries)

@webhook_bp.route('/retry/<int:id>', methods=['POST'])
def retry(id):
    try:
        uow = SqliteUnitOfWork()
        with uow:
            handler = current_app.di_container.get_retry_delivery_handler(uow)
            handler.handle(RetryWebhookDeliveryCommand(delivery_id=id))
        flash("Delivery marked for manual retry.", 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('webhooks.index'))