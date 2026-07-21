import pytest
import os
from decimal import Decimal
from src.common.infrastructure.database import Database, DB_PATH, create_connection
from src.common.infrastructure.event_bus import InMemoryEventBus
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.webhook.application.handlers.webhook_outbox_event_handler import WebhookOutboxEventHandler
from src.webhook.infrastructure.persistence.sqlite_webhook_outbox_repository import SqliteWebhookOutboxRepository
from src.webhook.infrastructure.persistence.sqlite_merchant_webhook_config_adapter import SqliteMerchantWebhookConfigAdapter
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.currency_code import CurrencyCode
from src.ledger.domain.events.transaction_events import TransactionCompletedEvent

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    Database.initialize()
    
    # Setup a merchant with webhooks enabled
    conn = create_connection()
    conn.execute(
        """INSERT INTO merchants (name, api_key, is_active, webhook_url, webhook_secret, webhook_enabled) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Test Merchant", "pay_test_key_12345678901234567890123456789012345678901", 1, "https://example.com/hook", "whsec_supersecret", 1)
    )
    conn.commit()
    merchant_id = conn.execute("SELECT id FROM merchants WHERE name = 'Test Merchant'").fetchone()['id']
    conn.close()
    
    yield merchant_id
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_webhook_outbox_inserts_record_atomically(setup_db):
    merchant_id = setup_db
    bus = InMemoryEventBus()
    merchant_config_adapter = SqliteMerchantWebhookConfigAdapter(connection_factory=create_connection)
    
    def get_handler():
        uow = SqliteUnitOfWork()
        return WebhookOutboxEventHandler(uow, SqliteWebhookOutboxRepository(uow), merchant_config_adapter)

    bus.subscribe(TransactionCompletedEvent, lambda e: get_handler().handle_completed(e))

    event = TransactionCompletedEvent(
        transaction_id="txn_123",
        payer_account_id="acc_123",
        amount=Money(amount=Decimal("100.00"), currency=CurrencyCode(value="USD")),
        merchant_id=merchant_id
    )

    # Simulate the parent business transaction
    with SqliteUnitOfWork():
        bus.publish(event)

    # Assert the outbox record was committed atomically
    conn = create_connection()
    record = conn.execute("SELECT * FROM webhook_outbox WHERE merchant_id = ?", (merchant_id,)).fetchone()
    conn.close()
    
    assert record is not None
    assert record['event_type'] == "payment.completed"
    assert record['status'] == "pending"
    assert record['attempts'] == 0
    assert "txn_123" in record['payload']
    assert len(record['signature']) == 64  # SHA256 hex digest length

def test_webhook_outbox_ignores_disabled_merchants(setup_db):
    merchant_id = setup_db
    # Disable webhook for the merchant
    conn = create_connection()
    conn.execute("UPDATE merchants SET webhook_enabled = 0 WHERE id = ?", (merchant_id,))
    conn.commit()
    conn.close()

    bus = InMemoryEventBus()
    merchant_config_adapter = SqliteMerchantWebhookConfigAdapter(connection_factory=create_connection)
    
    def get_handler():
        uow = SqliteUnitOfWork()
        return WebhookOutboxEventHandler(uow, SqliteWebhookOutboxRepository(uow), merchant_config_adapter)

    bus.subscribe(TransactionCompletedEvent, lambda e: get_handler().handle_completed(e))

    event = TransactionCompletedEvent(
        transaction_id="txn_456",
        payer_account_id="acc_123",
        amount=Money(amount=Decimal("50.00"), currency=CurrencyCode(value="USD")),
        merchant_id=merchant_id
    )

    with SqliteUnitOfWork():
        bus.publish(event)

    # Assert no new record was inserted
    conn = create_connection()
    records = conn.execute("SELECT * FROM webhook_outbox WHERE merchant_id = ? AND payload LIKE '%txn_456%'", (merchant_id,)).fetchall()
    conn.close()
    
    assert len(records) == 0