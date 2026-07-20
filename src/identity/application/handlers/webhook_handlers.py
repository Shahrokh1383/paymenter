import secrets
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.exceptions import NotFoundError
from src.identity.domain.repositories import MerchantRepository
from src.identity.application.commands.webhook_commands import (
    ConfigureWebhookCommand, 
    GenerateWebhookSecretCommand
)

class ConfigureWebhookHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository):
        self._uow = uow
        self._merchant_repo = merchant_repo

    def handle(self, cmd: ConfigureWebhookCommand) -> None:
        with self._uow:
            merchant = self._merchant_repo.get_by_id(cmd.merchant_id)
            if not merchant:
                raise NotFoundError(f"Merchant with id {cmd.merchant_id} not found.")
            
            merchant.configure_webhook(cmd.webhook_url, cmd.webhook_enabled)
            self._merchant_repo.update(merchant)
            self._uow.commit()

class GenerateWebhookSecretHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository):
        self._uow = uow
        self._merchant_repo = merchant_repo

    def handle(self, cmd: GenerateWebhookSecretCommand) -> str:
        with self._uow:
            merchant = self._merchant_repo.get_by_id(cmd.merchant_id)
            if not merchant:
                raise NotFoundError(f"Merchant with id {cmd.merchant_id} not found.")
            
            # Generate a cryptographically secure secret
            new_secret = "whsec_" + secrets.token_urlsafe(32)
            merchant.set_webhook_secret(new_secret)
            self._merchant_repo.update(merchant)
            self._uow.commit()
            
            return new_secret  # Returned once to be displayed to the admin