from typing import List
from src.webhook.application.dto.webhook_delivery_dto import WebhookDeliveryDTO
from src.webhook.domain.ports.webhook_delivery_query_port import WebhookDeliveryQueryPort
from src.webhook.application.queries.get_all_deliveries_query import GetAllDeliveriesQuery

class GetAllDeliveriesHandler:
    def __init__(self, repo: WebhookDeliveryQueryPort):
        self._repo = repo

    def handle(self, query: GetAllDeliveriesQuery) -> List[WebhookDeliveryDTO]:
        return self._repo.get_all()