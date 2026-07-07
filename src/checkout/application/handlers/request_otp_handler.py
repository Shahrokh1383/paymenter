from datetime import datetime, timedelta
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.ports.event_bus import EventBus
from src.common.domain.exceptions import DomainException
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.card_number import CardNumber
from src.checkout.domain.repositories import PaymentSessionRepository
from src.checkout.domain.ports.account_lookup_port import AccountLookupPort
from src.checkout.domain.ports.otp_generator import OtpGenerator
from src.checkout.domain.events.otp_requested_event import OtpRequestedEvent
from src.checkout.application.commands.request_otp_command import RequestOtpCommand
from src.common.domain.value_objects.email_address import EmailAddress

class RequestOtpHandler:
    def __init__(
        self, 
        uow: UnitOfWork, 
        session_repo: PaymentSessionRepository,
        lookup_port: AccountLookupPort,
        otp_gen: OtpGenerator,
        event_bus: EventBus
    ):
        self._uow = uow
        self._session_repo = session_repo
        self._lookup_port = lookup_port
        self._otp_gen = otp_gen
        self._event_bus = event_bus

    def handle(self, command: RequestOtpCommand) -> dict:
        # 1. Enforce Strict Typing
        token_vo = SessionToken(command.session_token)
        card_vo = CardNumber(command.card_number)
        
        with self._uow:
            session = self._session_repo.get_by_token(token_vo)
            
            # 2. Resolve Registered Email via ACL
            registered_email_str = self._lookup_port.get_email_by_card_number(card_vo.value)
            if not registered_email_str:
                raise DomainException("This card number is not registered in our system.")
            
            registered_email_vo = EmailAddress(registered_email_str)
                
            # 3. Generate OTP and Expiration (3 Minutes)
            otp_vo = self._otp_gen.generate()
            expires_at = datetime.utcnow() + timedelta(minutes=3)
            
            # 4. Mutate Aggregate & Persist
            session.request_otp(card_vo, otp_vo, expires_at)
            self._session_repo.update(session)
            self._uow.commit()

        # 5. Dispatch Event (OUTSIDE UoW) with strict Value Objects
        self._event_bus.publish(OtpRequestedEvent(
            session_token=session.token,
            registered_email=registered_email_vo,
            otp_code=otp_vo,
            merchant_name=session.merchant_name,
            amount=session.amount
        ))

        return {"expires_in_seconds": 180}