from src.common.domain.ports.unit_of_work import UnitOfWork
from src.ledger.domain.events.account_balance_updated_event import AccountBalanceUpdatedEvent

class OnAccountBalanceUpdatedHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: AccountBalanceUpdatedEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                "UPDATE user_summaries SET balance = ? WHERE account_id = ?",
                (str(event.new_balance.amount), event.account_id)
            )
            self._uow.commit()