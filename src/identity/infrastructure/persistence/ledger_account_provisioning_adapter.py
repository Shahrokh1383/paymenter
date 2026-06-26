from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.generators import generate_account_number, generate_card_number
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort
from src.ledger.domain.repositories import AccountRepository
from src.ledger.domain.entities.account import Account
from src.ledger.domain.value_objects.account_number import AccountNumber
from src.ledger.domain.value_objects.card_number import CardNumber
from src.common.domain.value_objects.money import Money

class LedgerAccountProvisioningAdapter(AccountProvisioningPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def create_default_account(self, user_id: int, currency_id: int) -> int:
        acc_num = generate_account_number(lambda x: False) # Simplified uniqueness
        card_num = generate_card_number(lambda x: False)
        
        # Direct SQL via UoW to avoid polluting Ledger Domain with DB-specific currency_id
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, card_number, balance) VALUES (?, ?, ?, ?, 0.0)",
            (user_id, currency_id, acc_num, card_num)
        )
        return cursor.lastrowid