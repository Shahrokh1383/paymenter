from typing import Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.infrastructure.generators import generate_account_number
from src.identity.domain.ports.account_provisioning_port import AccountProvisioningPort

class LedgerAccountProvisioningAdapter(AccountProvisioningPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def create_default_account(self, user_id: Optional[int], currency_id: int) -> int:
        acc_num = generate_account_number(lambda _: False)
        cursor = self._uow.conn.execute(
            "INSERT INTO accounts (user_id, currency_id, account_number, balance) VALUES (?, ?, ?, '0.00')",
            (user_id, currency_id, acc_num)
        )
        return cursor.lastrowid