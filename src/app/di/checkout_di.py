from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.checkout.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from src.checkout.infrastructure.persistence.ledger_fund_reservation_adapter import LedgerFundReservationAdapter
from src.checkout.infrastructure.persistence.identity_account_lookup_adapter import IdentityAccountLookupAdapter
from src.checkout.infrastructure.services.otp_generator import SecureOtpGenerator
from src.checkout.infrastructure.services.session_token_generator import SecureSessionTokenGenerator

from src.checkout.application.handlers.initiate_payment_handler import InitiatePaymentHandler
from src.checkout.application.handlers.request_otp_handler import RequestOtpHandler
from src.checkout.application.handlers.authorize_payment_handler import AuthorizePaymentHandler

def register_checkout(container):
    def get_initiate_payment_handler(uow: SqliteUnitOfWork) -> InitiatePaymentHandler:
        return InitiatePaymentHandler(
            uow=uow,
            session_repo=SqliteSessionRepository(uow),
            event_bus=container.event_bus,
            token_gen=SecureSessionTokenGenerator()
        )

    def get_request_otp_handler(uow: SqliteUnitOfWork) -> RequestOtpHandler:
        return RequestOtpHandler(
            uow=uow,
            session_repo=SqliteSessionRepository(uow),
            lookup_port=IdentityAccountLookupAdapter(uow),
            otp_gen=SecureOtpGenerator(),
            event_bus=container.event_bus
        )

    def get_authorize_payment_handler(uow: SqliteUnitOfWork) -> AuthorizePaymentHandler:
        return AuthorizePaymentHandler(
            uow=uow,
            session_repo=SqliteSessionRepository(uow),
            fund_port=LedgerFundReservationAdapter(uow),
            lookup_port=IdentityAccountLookupAdapter(uow)
        )

    container.get_initiate_payment_handler = get_initiate_payment_handler
    container.get_request_otp_handler = get_request_otp_handler
    container.get_authorize_payment_handler = get_authorize_payment_handler