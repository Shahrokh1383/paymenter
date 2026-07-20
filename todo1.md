



### Phase 5: Cryptographic Engine (Utility)
**What we will build:**
- A `WebhookSigner` utility class (infrastructure, not domain) that takes the raw JSON payload (as a string) and the merchant’s secret and returns `HMAC-SHA256(payload, secret)`. The signature is then stored in the outbox to avoid re‑signing on every retry.
- The outgoing HTTP headers are assembled by the worker using the pre‑computed signature.

---

## 🧩 Revised Summary of Deliverables

| Component | Description | Priority |
| :--- | :--- | :--- |
| **Domain Event** | Add `TransactionCompletedEvent` and publish it on successful completion. | High |
| **Identity Context** | Extend Merchant aggregate with webhook fields + secret generation. | High |
| **Outbox Table** | `webhook_outbox` table and repository for atomic persistence. | High |
| **Event Handlers** | Subscribers to domain events that convert them to outbox records (inside the UoW). | High |
| **Worker Process** | Background process that reads outbox, sends HTTP POST with HMAC headers, and applies retry policy. | High |
| **Signer Utility** | HMAC-SHA256 generation (infra adapter). | High |
| **Admin UI** | Settings page for webhook URL/secret, log viewer, and manual retry button. | Medium |
| **Retry Policy** | Domain service for exponential backoff scheduling. | Medium |

---

## 🔄 How This Differs from Your Original Blueprint

- **No direct call from admin controllers.** The admin actions only cause domain events; the event handlers produce outbox records.
- **Atomicity guaranteed** by the outbox pattern (events are never lost, even on crash).
- **The HTTP dispatch is completely detached** from the request/response cycle, via a background worker.
- **Webhook configuration** lives in the Identity context (where the Merchant aggregate already exists), not in a new silo.
- **The whole system remains modular**, with clear boundaries: the webhook sending is an **infrastructure adapter** driven by domain events.

---
