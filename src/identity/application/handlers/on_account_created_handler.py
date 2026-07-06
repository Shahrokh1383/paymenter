from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.infrastructure.generators import generate_card_number
from src.ledger.domain.events.account_events import AccountCreatedEvent
from src.identity.domain.events.card_events import CardAssignedEvent

class OnAccountCreatedHandler:
    def __init__(self, uow: UnitOfWork, event_bus: EventBus):
        self._uow = uow
        self._event_bus = event_bus

    def handle(self, event: AccountCreatedEvent) -> None:
        if event.user_id is None and event.merchant_id is None:
            return

        with self._uow:
            card_number = generate_card_number(lambda _: False)
            self._uow.conn.execute(
                "INSERT INTO user_cards (user_id, merchant_id, account_id, card_number) VALUES (?, ?, ?, ?)",
                (event.user_id, event.merchant_id, event.account_id, card_number)
            )
            self._uow.commit()
            self._event_bus.publish(CardAssignedEvent(
                account_id=event.account_id,
                user_id=event.user_id,
                merchant_id=event.merchant_id,
                card_number=card_number
            ))