import hmac
import hashlib

class WebhookSigner:
    @staticmethod
    def sign(payload: str, secret: str) -> str:
        return hmac.new(
            key=secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()