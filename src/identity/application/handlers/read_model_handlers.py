from src.common.domain.ports.unit_of_work import UnitOfWork
from src.identity.domain.events.user_events import UserRegisteredEvent
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.identity.domain.events.card_events import CardAssignedEvent

class UserRegisteredReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: UserRegisteredEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                "INSERT INTO user_summaries (user_id, name, phone_email) VALUES (?, ?, ?)",
                (event.user_id, event.name, str(event.phone_email))
            )
            self._uow.commit()

class AccountCreatedReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: AccountCreatedEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                """UPDATE user_summaries SET 
                   account_id = ?, account_number = ?, currency_code = ?, balance = '0.00'
                   WHERE user_id = ?""",
                (event.account_id, str(event.account_number), str(event.currency_code), event.user_id)
            )
            self._uow.commit()

class CardAssignedReadModelHandler:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def handle(self, event: CardAssignedEvent) -> None:
        with self._uow:
            self._uow.conn.execute(
                "UPDATE user_summaries SET card_number = ? WHERE account_id = ?",
                (event.card_number, event.account_id)
            )
            self._uow.commit()