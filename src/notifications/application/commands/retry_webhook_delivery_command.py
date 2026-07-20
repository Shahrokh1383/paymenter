from dataclasses import dataclass

@dataclass(frozen=True)
class RetryWebhookDeliveryCommand:
    delivery_id: int