from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.ledger.application.commands.toggle_currency_command import ToggleCurrencyCommand
from src.ledger.domain.repositories import CurrencyRepository
from src.ledger.domain.events.currency_events import CurrencyActivatedEvent, CurrencyDeactivatedEvent
from src.common.domain.exceptions import CurrencyNotFoundError

class ToggleCurrencyHandler:
    def __init__(
        self, 
        uow: UnitOfWork, 
        currency_repo: CurrencyRepository,
        event_bus: EventBus
    ):
        self._uow = uow
        self._currency_repo = currency_repo
        self._event_bus = event_bus

    def handle(self, command: ToggleCurrencyCommand) -> None:
        with self._uow:
            currency = self._currency_repo.get_by_id(command.currency_id)
            if not currency:
                raise CurrencyNotFoundError(f"Currency with id {command.currency_id} not found.")

            was_active = currency.is_active
            currency.toggle()
            
            self._currency_repo.update(currency)
            self._uow.commit()
            
            if was_active:
                self._event_bus.publish(CurrencyDeactivatedEvent(currency_id=currency.id, code=currency.code))
            else:
                self._event_bus.publish(CurrencyActivatedEvent(currency_id=currency.id, code=currency.code))