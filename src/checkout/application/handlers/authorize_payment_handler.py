from typing import Tuple
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.exceptions import DomainException
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.card_number import CardNumber # NEW
from src.checkout.domain.repositories import PaymentSessionRepository
from src.checkout.domain.ports.fund_reservation_port import FundReservationPort
from src.checkout.domain.ports.account_lookup_port import AccountLookupPort
from src.checkout.application.commands.authorize_payment_command import AuthorizePaymentCommand

class AuthorizePaymentHandler:
    def __init__(
        self, 
        uow: UnitOfWork, 
        session_repo: PaymentSessionRepository,
        fund_port: FundReservationPort,
        lookup_port: AccountLookupPort
    ):
        self._uow = uow
        self._session_repo = session_repo
        self._fund_port = fund_port
        self._lookup_port = lookup_port

    def handle(self, command: AuthorizePaymentCommand) -> Tuple[int, str]:
        token_vo = SessionToken(command.session_token)
        card_vo = CardNumber(command.card_number)
        
        with self._uow:
            session = self._session_repo.get_by_token(token_vo)
            
            # Validate State, Card Match, Expiration, and OTP
            session.authorize(card_vo, command.otp_input)
            
            from_account_id = self._lookup_port.get_account_id_by_card_number(card_vo.value)
            if not from_account_id:
                raise DomainException("Card number not found in our system.")
                
            to_account_id = self._lookup_port.get_settlement_account_id(session.merchant_id, session.amount.currency)
            if not to_account_id:
                raise DomainException("Merchant settlement configuration error.")

            txn_id = self._fund_port.hold_funds(
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount=session.amount.amount,
                currency_code=session.amount.currency,
                merchant_id=session.merchant_id,
                user_email=session.user_email.value
            )

            session.attach_transaction(txn_id)
            self._session_repo.update(session)
            self._uow.commit()

            return txn_id, session.callback_url.value