from typing import Optional
from decimal import Decimal
from src.common.domain.ports.unit_of_work import UnitOfWork
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.email_address import EmailAddress
from src.checkout.domain.entities.payment_session import PaymentSession
from src.checkout.domain.value_objects.session_token import SessionToken
from src.checkout.domain.value_objects.otp_code import OtpCode
from src.checkout.domain.value_objects.callback_url import CallbackUrl
from src.checkout.domain.repositories import PaymentSessionRepository

class SqliteSessionRepository(PaymentSessionRepository):
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def save(self, session: PaymentSession) -> int:
        cursor = self._uow.conn.execute("""
            INSERT INTO gateway_sessions 
            (token, merchant_id, amount, currency_id, user_email, callback_url, status)
            VALUES (?, ?, ?, (SELECT id FROM currencies WHERE code = ?), ?, ?, ?)
        """, (
            session.token.value,
            session.merchant_id,
            str(session.amount.amount),
            session.amount.currency,
            session.user_email.value,
            session.callback_url.value,
            session.status
        ))
        object.__setattr__(session, 'id', cursor.lastrowid)
        return cursor.lastrowid

    def update(self, session: PaymentSession) -> None:
        self._uow.conn.execute("""
            UPDATE gateway_sessions 
            SET status = ?, transaction_id = ?, otp_code = ?, otp_locked_card = ?, otp_expires_at = ?
            WHERE token = ?
        """, (
            session.status, 
            session.transaction_id, 
            session.otp_code.value if session.otp_code else None,
            session.otp_locked_card,
            session.otp_expires_at.isoformat() if session.otp_expires_at else None,
            session.token.value
        ))

    def get_by_token(self, token: SessionToken) -> PaymentSession:
        row = self._uow.conn.execute("""
            SELECT gs.*, m.name as merchant_name, c.code as currency_code 
            FROM gateway_sessions gs
            JOIN merchants m ON gs.merchant_id = m.id
            JOIN currencies c ON gs.currency_id = c.id
            WHERE gs.token = ?
        """, (token.value,)).fetchone()
        
        if not row:
            raise ValueError("Payment session not found.")

        # Parse datetime safely
        expires_at = None
        if row['otp_expires_at']:
            from datetime import datetime
            expires_at = datetime.fromisoformat(row['otp_expires_at'])

        return PaymentSession(
            id=row['id'],
            token=SessionToken(row['token']),
            merchant_id=row['merchant_id'],
            merchant_name=row['merchant_name'],
            amount=Money(Decimal(str(row['amount'])), row['currency_code']),
            user_email=EmailAddress(row['user_email']),
            callback_url=CallbackUrl(row['callback_url']),
            status=row['status'],
            transaction_id=row['transaction_id'],
            otp_code=OtpCode(row['otp_code']) if row['otp_code'] else None,
            otp_locked_card=row['otp_locked_card'],
            otp_expires_at=expires_at
        )

    def exists_by_token(self, token_value: str) -> bool:
        row = self._uow.conn.execute(
            "SELECT 1 FROM gateway_sessions WHERE token = ?", (token_value,)
        ).fetchone()
        return row is not None