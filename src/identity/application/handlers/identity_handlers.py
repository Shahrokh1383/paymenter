from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.infrastructure.generators import generate_api_key
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.entities.currency import Currency
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.repositories import MerchantRepository, CurrencyRepository
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort
from src.identity.domain.events.merchant_events import (
    MerchantOnboardedEvent,
    MerchantActivatedEvent,
    MerchantDeactivatedEvent
)
from src.identity.application.commands.identity_commands import (
    OnboardMerchantCommand, ToggleMerchantCommand, AddCurrencyCommand, ToggleCurrencyCommand
)


class OnboardMerchantHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        merchant_repo: MerchantRepository,
        account_port: AccountProvisioningPort,
        currency_repo: CurrencyRepository,
        event_bus: EventBus
    ):
        self._uow = uow
        self._merchant_repo = merchant_repo
        self._account_port = account_port
        self._currency_repo = currency_repo
        self._event_bus = event_bus

    def handle(self, cmd: OnboardMerchantCommand) -> None:
        with self._uow:
            active_currencies = self._currency_repo.get_active()
            if not active_currencies:
                raise ValueError("No active currencies found. Please add a currency first.")
            settlement_currency = sorted(active_currencies, key=lambda c: c.id)[0]

            settlement_account_id = self._account_port.create_default_account(
                None, settlement_currency.id
            )

            api_key = ApiKey(generate_api_key())
            merchant = Merchant(
                id=0,
                name=cmd.name,
                api_key=api_key,
                is_active=True,
                settlement_account_id=settlement_account_id
            )

            merchant_id = self._merchant_repo.add(merchant)
            merchant.id = merchant_id

            self._uow.commit()

            self._event_bus.publish(
                MerchantOnboardedEvent(
                    merchant_id=merchant.id,
                    name=merchant.name,
                    api_key=merchant.api_key
                )
            )
class ToggleMerchantHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository, event_bus: EventBus):
        self._uow = uow
        self._merchant_repo = merchant_repo
        self._event_bus = event_bus

    def handle(self, cmd: ToggleMerchantCommand) -> None:
        with self._uow:
            merchant = self._merchant_repo.get_by_id(cmd.merchant_id)
            if not merchant:
                raise ValueError(f"Merchant with id {cmd.merchant_id} not found.")

            merchant.toggle()

            self._merchant_repo.update(merchant)
            self._uow.commit()

            event = (
                MerchantActivatedEvent(merchant_id=merchant.id)
                if merchant.is_active
                else MerchantDeactivatedEvent(merchant_id=merchant.id)
            )
            self._event_bus.publish(event)
class AddCurrencyHandler:
    def __init__(self, uow: UnitOfWork, currency_repo: CurrencyRepository):
        self._uow, self._currency_repo = uow, currency_repo

    def handle(self, cmd: AddCurrencyCommand) -> None:
        with self._uow:
            if self._currency_repo.exists_by_code(cmd.code):
                raise ValueError("Currency code already exists.")
            currency = Currency(id=0, name=cmd.name, code=cmd.code, is_active=True)
            self._currency_repo.add(currency)
            self._uow.commit()
class ToggleCurrencyHandler:
    def __init__(self, uow: UnitOfWork, currency_repo: CurrencyRepository):
        self._uow, self._currency_repo = uow, currency_repo

    def handle(self, cmd: ToggleCurrencyCommand) -> None:
        with self._uow:
            self._currency_repo.toggle_status(cmd.currency_id)
            self._uow.commit()