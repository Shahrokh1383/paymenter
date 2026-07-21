import requests
from src.webhook.domain.ports.http_client_port import HttpClientPort

class RequestsHttpClientAdapter(HttpClientPort):
    def post(self, url: str, headers: dict, body: str) -> int:
        response = requests.post(url, headers=headers, data=body, timeout=10)
        return response.status_code