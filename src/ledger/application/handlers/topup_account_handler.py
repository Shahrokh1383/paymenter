from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.value_objects.money import Money
from src.ledger.domain.repositories import AccountRepository
from src.ledger.application.commands.topup_account_command import TopupAccountCommand
from src.ledger.domain.events.account_balance_updated_event import AccountBalanceUpdatedEvent

class TopupAccountHandler:
    def __init__(self, uow: UnitOfWork, account_repo: AccountRepository, event_bus: EventBus):
        self._uow = uow
        self._account_repo = account_repo
        self._event_bus = event_bus

    def handle(self, command: TopupAccountCommand) -> None:
        account = None
        with self._uow:
            account = self._account_repo.get_by_id(command.account_id)
            if not account:
                raise ValueError("Account not found")
            topup_money = Money(command.amount, account.balance.currency)
            account.topup(topup_money)
            self._account_repo.update(account)
            self._uow.commit()

        if account:
            self._event_bus.publish(AccountBalanceUpdatedEvent(
                account_id=account.id,
                user_id=account.user_id,
                new_balance=account.balance
            ))