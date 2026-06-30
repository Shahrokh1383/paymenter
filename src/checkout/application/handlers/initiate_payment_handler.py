from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.email_address import EmailAddress
from src.checkout.domain.entities.payment_session import PaymentSession
from src.checkout.domain.value_objects.callback_url import CallbackUrl
from src.checkout.domain.repositories import PaymentSessionRepository
from src.checkout.domain.ports.session_token_generator import SessionTokenGenerator
from src.checkout.domain.events.payment_initiated_event import PaymentInitiatedEvent
from src.checkout.application.commands.initiate_payment_command import InitiatePaymentCommand

class InitiatePaymentHandler:
    def __init__(
        self, 
        uow: UnitOfWork, 
        session_repo: PaymentSessionRepository,
        event_bus: EventBus,
        token_gen: SessionTokenGenerator
    ):
        self._uow = uow
        self._session_repo = session_repo
        self._event_bus = event_bus
        self._token_gen = token_gen

    def handle(self, command: InitiatePaymentCommand) -> str:
        token_vo = self._token_gen.generate(lambda t: self._session_repo.exists_by_token(t))
        money_vo = Money(command.amount, command.currency_code)
        email_vo = EmailAddress(command.user_email)
        url_vo = CallbackUrl(command.callback_url)

        # Create Aggregate WITHOUT OTP
        session = PaymentSession(
            id=0,
            token=token_vo,
            merchant_id=command.merchant_id,
            merchant_name=command.merchant_name,
            amount=money_vo,
            user_email=email_vo,
            callback_url=url_vo
        )

        with self._uow:
            self._session_repo.save(session)
            self._uow.commit()

        self._event_bus.publish(PaymentInitiatedEvent(
            session_token=token_vo.value,
            user_email=email_vo.value,
            merchant_name=command.merchant_name,
            amount=str(money_vo.amount),
            currency_code=money_vo.currency
        ))

        return token_vo.value