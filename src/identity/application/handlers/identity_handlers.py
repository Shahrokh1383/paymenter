from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.generators import generate_api_key
from src.identity.domain.entities.user import User
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.entities.currency import Currency
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.repositories import UserRepository, MerchantRepository, CurrencyRepository
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort
from src.identity.application.commands.identity_commands import (
    OnboardMerchantCommand, ToggleMerchantCommand, AddCurrencyCommand, ToggleCurrencyCommand
)

class OnboardMerchantHandler:
    def __init__(self, uow: UnitOfWork, user_repo: UserRepository, merchant_repo: MerchantRepository, account_port: AccountProvisioningPort):
        self._uow, self._user_repo, self._merchant_repo, self._account_port = uow, user_repo, merchant_repo, account_port

    def handle(self, cmd: OnboardMerchantCommand) -> None:
        with self._uow:
            # 1. Create system user for settlement
            user = User(id=0, name=f"Merchant: {cmd.name}", phone_email=f"system_merchant_{cmd.name}@paymenter.com")
            user_id = self._user_repo.add(user)
            
            # 2. Provision settlement account via ACL (Currency ID 1 = Toman)
            settlement_acc_id = self._account_port.create_default_account(user_id, 1)
            
            # 3. Create Merchant Aggregate
            merchant = Merchant(id=0, name=cmd.name, api_key=ApiKey(generate_api_key()), is_active=True, settlement_account_id=settlement_acc_id)
            self._merchant_repo.add(merchant)
            self._uow.commit()

class ToggleMerchantHandler:
    def __init__(self, uow: UnitOfWork, merchant_repo: MerchantRepository):
        self._uow, self._merchant_repo = uow, merchant_repo

    def handle(self, cmd: ToggleMerchantCommand) -> None:
        with self._uow:
            # Note: For simplicity in this simulator, we fetch and update directly via SQL in the repo
            self._merchant_repo.toggle_status(cmd.merchant_id)
            self._uow.commit()

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