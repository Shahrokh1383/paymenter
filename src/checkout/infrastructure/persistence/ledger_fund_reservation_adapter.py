from decimal import Decimal
from typing import Optional
from src.checkout.domain.ports.fund_reservation_port import FundReservationPort
from src.ledger.application.commands.hold_funds_command import HoldFundsCommand
from src.ledger.application.handlers.hold_funds_handler import HoldFundsHandler

class LedgerFundReservationAdapter(FundReservationPort):
    """
    Anti-Corruption Layer Port for reserving funds in the Ledger.
    Receives the fully constructed Ledger handler via DI to avoid tight coupling.
    """
    
    def __init__(self, ledger_handler: HoldFundsHandler):
        self._ledger_handler = ledger_handler

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
        return self._ledger_handler.handle(command)