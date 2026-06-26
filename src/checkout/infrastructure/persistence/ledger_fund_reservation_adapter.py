from decimal import Decimal
from typing import Optional
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.checkout.domain.ports.fund_reservation_port import FundReservationPort
# Importing Ledger's Application Handler is ALLOWED in Infrastructure ACL
from src.ledger.application.commands.hold_funds_command import HoldFundsCommand
from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler
from src.ledger.infrastructure.persistence.sqlite_account_repository import SqliteAccountRepository
from src.ledger.infrastructure.persistence.sqlite_transaction_repository import SqliteTransactionRepository

class LedgerFundReservationAdapter(FundReservationPort):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow
        # Wire up the Ledger's handler internally
        self._ledger_handler = HoldFundsHandler(
            uow=self._uow,
            account_repo=SqliteAccountRepository(self._uow),
            txn_repo=SqliteTransactionRepository(self._uow)
        )

    def hold_funds(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
        currency_code: str,
        merchant_id: Optional[int] = None,
        user_email: Optional[str] = None
    ) -> int:
        command = HoldFundsCommand(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            merchant_id=merchant_id,
            user_email=user_email
        )
        # The handler internally manages the UoW and Domain logic
        return self._ledger_handler.handle(command)