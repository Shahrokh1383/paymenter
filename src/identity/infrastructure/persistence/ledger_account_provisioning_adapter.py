from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.generators import generate_account_number, generate_card_number
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort

class LedgerAccountProvisioningAdapter(AccountProvisioningPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def create_default_account(self, user_id: int, currency_id: int) -> int:
        acc_num = generate_account_number(lambda x: False) # Simplified uniqueness
        card_num = generate_card_number(lambda x: False)
        
        # 1. Create Ledger account WITHOUT card_number (Respects Ledger Bounded Context)
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, balance) VALUES (?, ?, ?, '0.00')",
            (user_id, currency_id, acc_num)
        )
        account_id = cursor.lastrowid
        
        # 2. Store card mapping in Identity context (user_cards table)
        self._uow.conn.execute(
            "INSERT INTO user_cards (user_id, account_id, card_number) VALUES (?, ?, ?)",
            (user_id, account_id, card_num)
        )
        
        return account_id