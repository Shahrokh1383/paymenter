import time
import logging
from src.common.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from src.notifications.infrastructure.persistence.sqlite_webhook_delivery_repository import SqliteWebhookDeliveryRepository
from src.notifications.infrastructure.adapters.requests_http_client_adapter import RequestsHttpClientAdapter
from src.notifications.infrastructure.persistence.sqlite_merchant_webhook_config_adapter import SqliteMerchantWebhookConfigAdapter
from src.common.infrastructure.database import create_connection
from src.notifications.domain.services.webhook_retry_policy import WebhookRetryPolicy

logger = logging.getLogger(__name__)

def run_worker():
    """Main loop for the background webhook forwarder."""
    logger.info("Starting Webhook Forwarder Worker...")
    http_client = RequestsHttpClientAdapter()
    merchant_config_adapter = SqliteMerchantWebhookConfigAdapter(connection_factory=create_connection)
    
    while True:
        try:
            with SqliteUnitOfWork() as uow:
                repo = SqliteWebhookDeliveryRepository(uow)
                pending_deliveries = repo.get_pending()
                
                for delivery in pending_deliveries:
                    config = merchant_config_adapter.get_config(delivery.merchant_id)
                    if not config or not config.webhook_url:
                        logger.error(f"No webhook URL for merchant {delivery.merchant_id}. Marking delivery {delivery.id} as failed.")
                        repo.mark_as_failed(delivery.id)
                        continue
                        
                    headers = {
                        "Content-Type": "application/json",
                        "X-Paymenter-Signature": f"sha256={delivery.signature}",
                        "X-Paymenter-Event": delivery.event_type,
                        "X-Paymenter-Delivery": str(delivery.id)
                    }
                    
                    try:
                        status_code = http_client.post(config.webhook_url, headers, delivery.payload)
                        if 200 <= status_code < 300:
                            logger.info(f"Delivery {delivery.id} sent successfully.")
                            repo.mark_as_sent(delivery.id)
                        else:
                            raise Exception(f"HTTP {status_code}")
                    except Exception as e:
                        logger.warning(f"Delivery {delivery.id} failed: {e}")
                        attempts = delivery.attempts + 1
                        if attempts >= WebhookRetryPolicy.MAX_ATTEMPTS:
                            logger.error(f"Delivery {delivery.id} reached max attempts. Marking as failed.")
                            repo.mark_as_failed(delivery.id)
                        else:
                            next_attempt = WebhookRetryPolicy.calculate_next_attempt(attempts)
                            repo.record_retry(delivery.id, attempts, next_attempt)
                uow.commit()
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            
        time.sleep(10) # Poll every 10 seconds