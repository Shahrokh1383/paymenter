from src.common.domain.ports.unit_of_work import UnitOfWork
from src.checkout.domain.ports.transaction_refund_port import TransactionRefundPort
from src.checkout.application.commands.refund_payment_command import RefundPaymentCommand

class RefundPaymentHandler:
    def __init__(self, uow: UnitOfWork, refund_port: TransactionRefundPort):
        self._uow = uow
        self._refund_port = refund_port

    def handle(self, command: RefundPaymentCommand) -> None:
        with self._uow:
            self._refund_port.refund_or_fail(command.transaction_id)
            self._uow.commit()