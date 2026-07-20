import hmac
import hashlib

class WebhookSigner:
    """Utility class for generating HMAC-SHA256 signatures for webhook payloads."""
    
    @staticmethod
    def sign(payload: str, secret: str) -> str:
        """Generates a hex digest of the HMAC-SHA256 signature."""
        return hmac.new(
            key=secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()