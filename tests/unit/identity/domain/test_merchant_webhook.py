import pytest
from src.identity.domain.entities.merchant import Merchant
from src.identity.domain.value_objects.api_key import ApiKey
from src.identity.domain.value_objects.webhook_url import WebhookUrl

@pytest.fixture
def valid_api_key():
    return ApiKey("pay_" + "a" * 43)

def test_merchant_configure_webhook_valid_url(valid_api_key):
    merchant = Merchant(id=1, name="Test", api_key=valid_api_key, is_active=True)
    merchant.configure_webhook("https://example.com/webhook", True)
    assert merchant.webhook_url == WebhookUrl("https://example.com/webhook")
    assert merchant.webhook_enabled is True

def test_merchant_configure_webhook_invalid_url(valid_api_key):
    merchant = Merchant(id=1, name="Test", api_key=valid_api_key, is_active=True)
    with pytest.raises(ValueError, match="valid absolute URL"):
        merchant.configure_webhook("not-a-url", True)

def test_merchant_enable_webhook_without_url_raises_error(valid_api_key):
    merchant = Merchant(id=1, name="Test", api_key=valid_api_key, is_active=True)
    with pytest.raises(ValueError, match="Cannot enable webhook without providing a valid URL."):
        merchant.configure_webhook(None, True)

def test_merchant_set_webhook_secret(valid_api_key):
    merchant = Merchant(id=1, name="Test", api_key=valid_api_key, is_active=True)
    secret = "whsec_supersecretstring123456"
    merchant.set_webhook_secret(secret)
    assert merchant.webhook_secret == secret

def test_merchant_set_invalid_webhook_secret(valid_api_key):
    merchant = Merchant(id=1, name="Test", api_key=valid_api_key, is_active=True)
    with pytest.raises(ValueError, match="at least 20 characters"):
        merchant.set_webhook_secret("short")