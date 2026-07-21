import secrets
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.exceptions import NotFoundError
from src.identity.domain.repositories import MerchantRepository
from src.identity.domain.events.merchant_events import (
    MerchantWebhookConfiguredEvent,
    MerchantWebhookSecretGeneratedEvent
)
from src.identity.application.commands.webhook_commands import (
    ConfigureWebhookCommand, 
    GenerateWebhookSecretCommand
)

class ConfigureWebhookHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository, event_bus: EventBus):
        self._uow = uow
        self._merchant_repo = merchant_repo
        self._event_bus = event_bus

    def handle(self, cmd: ConfigureWebhookCommand) -> None:
        with self._uow:
            merchant = self._merchant_repo.get_by_id(cmd.merchant_id)
            if not merchant:
                raise NotFoundError(f"Merchant with id {cmd.merchant_id} not found.")
            
            merchant.configure_webhook(cmd.webhook_url, cmd.webhook_enabled)
            self._merchant_repo.update(merchant)
            self._uow.commit()

        # Post-commit projection trigger
        self._event_bus.publish(
            MerchantWebhookConfiguredEvent(
                merchant_id=merchant.id,
                webhook_url=merchant.webhook_url.value if merchant.webhook_url else None,
                webhook_enabled=merchant.webhook_enabled
            )
        )

class GenerateWebhookSecretHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository, event_bus: EventBus):
        self._uow = uow
        self._merchant_repo = merchant_repo
        self._event_bus = event_bus

    def handle(self, cmd: GenerateWebhookSecretCommand) -> str:
        with self._uow:
            merchant = self._merchant_repo.get_by_id(cmd.merchant_id)
            if not merchant:
                raise NotFoundError(f"Merchant with id {cmd.merchant_id} not found.")
            
            new_secret = "whsec_" + secrets.token_urlsafe(32)
            merchant.set_webhook_secret(new_secret)
            self._merchant_repo.update(merchant)
            self._uow.commit()
            
        self._event_bus.publish(MerchantWebhookSecretGeneratedEvent(merchant_id=merchant.id))
        return new_secret