import pytest
import os
from datetime import datetime, timedelta, timezone
from src.common.infrastructure.database import Database, DB_PATH, create_connection
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.webhook.infrastructure.persistence.sqlite_webhook_delivery_repository import SqliteWebhookDeliveryRepository
from src.webhook.domain.services.webhook_retry_policy import WebhookRetryPolicy

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    Database.initialize()
    
    # Insert a mock merchant and delivery
    conn = create_connection()
    conn.execute(
        """INSERT INTO merchants (name, api_key, is_active) VALUES (?, ?, ?)""",
        ("Test Merchant", "pay_test_key_12345678901234567890123456789012345678901", 1)
    )
    conn.execute(
        """INSERT INTO webhook_outbox (merchant_id, event_type, payload, status, attempts, signature) 
           VALUES (?, ?, ?, 'pending', 0, ?)""",
        (1, "payment.completed", "{}", "sig")
    )
    conn.commit()
    delivery_id = conn.execute("SELECT id FROM webhook_outbox").fetchone()['id']
    conn.close()
    
    yield delivery_id
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_retry_policy_calculates_next_attempt():
    next_attempt = WebhookRetryPolicy.calculate_next_attempt(0)
    assert next_attempt is not None
    assert next_attempt > datetime.now(timezone.utc)
    
    next_attempt_5 = WebhookRetryPolicy.calculate_next_attempt(5)
    assert next_attempt_5 is None  # Max attempts reached

def test_delivery_repo_mark_as_sent(setup_db):
    delivery_id = setup_db
    uow = SqliteUnitOfWork()
    with uow:
        repo = SqliteWebhookDeliveryRepository(uow)
        repo.mark_as_sent(delivery_id)
        uow.commit()
        
    conn = create_connection()
    record = conn.execute("SELECT * FROM webhook_outbox WHERE id = ?", (delivery_id,)).fetchone()
    conn.close()
    assert record['status'] == 'sent'
    assert record['attempts'] == 1

def test_delivery_repo_record_retry_and_get_pending(setup_db):
    delivery_id = setup_db
    uow = SqliteUnitOfWork()
    with uow:
        repo = SqliteWebhookDeliveryRepository(uow)
        # Reset to pending for this test
        repo.mark_for_retry(delivery_id)
        uow.commit()
        
        pending = repo.get_pending()
        assert len(pending) > 0
        
        next_attempt = datetime.now(timezone.utc) + timedelta(minutes=5)
        repo.record_retry(delivery_id, 1, next_attempt)
        uow.commit()
        
    conn = create_connection()
    record = conn.execute("SELECT * FROM webhook_outbox WHERE id = ?", (delivery_id,)).fetchone()
    conn.close()
    assert record['attempts'] == 1