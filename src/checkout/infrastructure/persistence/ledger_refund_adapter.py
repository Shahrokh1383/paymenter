from src.checkout.domain.ports.transaction_refund_port import TransactionRefundPort
from src.ledger.application.handlers.fail_and_refund_handler import FailAndRefundHandler
from src.ledger.application.commands.fail_and_refund_command import FailAndRefundCommand

class LedgerRefundAdapter(TransactionRefundPort):
    def __init__(self, ledger_handler: FailAndRefundHandler):
        self._ledger_handler = ledger_handler

    def refund_or_fail(self, transaction_id: int) -> None:
        command = FailAndRefundCommand(transaction_id=transaction_id)
        self._ledger_handler.handle(command)