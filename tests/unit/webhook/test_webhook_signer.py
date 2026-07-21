import pytest
from src.webhook.infrastructure.utils.webhook_signer import WebhookSigner

def test_webhook_signer_generates_correct_signature():
    payload = '{"event":"payment.completed","transaction_id":"txn_123"}'
    secret = "whsec_supersecret"
    
    import hmac
    import hashlib
    expected_signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    actual_signature = WebhookSigner.sign(payload, secret)
    
    assert actual_signature == expected_signature
    assert len(actual_signature) == 64

def test_webhook_signer_consistent_for_same_input():
    payload = '{"event":"payment.failed"}'
    secret = "another_secret"
    
    sig1 = WebhookSigner.sign(payload, secret)
    sig2 = WebhookSigner.sign(payload, secret)
    
    assert sig1 == sig2

def test_webhook_signer_different_for_different_payloads():
    secret = "another_secret"
    
    sig1 = WebhookSigner.sign('{"event":"payment.completed"}', secret)
    sig2 = WebhookSigner.sign('{"event":"payment.refunded"}', secret)
    
    assert sig1 != sig2