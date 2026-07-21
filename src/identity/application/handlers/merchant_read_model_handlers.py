from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.events.merchant_events import (
    MerchantOnboardedEvent,
    MerchantActivatedEvent,
    MerchantDeactivatedEvent,
    MerchantWebhookConfiguredEvent
)

class MerchantOnboardedReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: MerchantOnboardedEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                "INSERT INTO merchant_summaries (id, name, api_key, is_active) VALUES (?, ?, ?, 1)",
                (event.merchant_id, event.name, event.api_key.value)
            )
            self._uow.commit()

class MerchantToggledReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle_activated(self, event: MerchantActivatedEvent) -> None:
        with self._uow:
            self._uow.conn.execute("UPDATE merchant_summaries SET is_active = 1 WHERE id = ?", (event.merchant_id,))
            self._uow.commit()

    def handle_deactivated(self, event: MerchantDeactivatedEvent) -> None:
        with self._uow:
            self._uow.conn.execute("UPDATE merchant_summaries SET is_active = 0 WHERE id = ?", (event.merchant_id,))
            self._uow.commit()

class MerchantWebhookConfiguredReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: MerchantWebhookConfiguredEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                "UPDATE merchant_summaries SET webhook_url = ?, webhook_enabled = ? WHERE id = ?",
                (event.webhook_url, event.webhook_enabled, event.merchant_id)
            )
            self._uow.commit()