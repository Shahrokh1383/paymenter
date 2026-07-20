from src.common.domain.ports.unit_of_work import UnitOfWork
from src.notifications.domain.ports.webhook_delivery_processor_port import WebhookDeliveryProcessorPort
from src.notifications.application.commands.retry_webhook_delivery_command import RetryWebhookDeliveryCommand

class RetryWebhookDeliveryHandler:
    def __init__(self, uow: UnitOfWork, repo: WebhookDeliveryProcessorPort):
        self._uow = uow
        self._repo = repo

    def handle(self, cmd: RetryWebhookDeliveryCommand) -> None:
        with self._uow:
            self._repo.mark_for_retry(cmd.delivery_id)
            self._uow.commit()