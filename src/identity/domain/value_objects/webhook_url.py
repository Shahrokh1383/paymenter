from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class WebhookUrl:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not self.value:
            raise ValueError("WebhookUrl must be a non-empty string.")
        parsed = urlparse(self.value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError("WebhookUrl must be a valid absolute URL (http/https).")