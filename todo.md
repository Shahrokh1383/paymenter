## 🧱 Revised Blueprint: Constitution‑Compliant Webhook System

### Principle: Webhooks are a *side effect* of Domain Events.
When an admin clicks **[Complete]**, that button calls a Ledger handler which mutates the `Transaction` aggregate and publishes a `TransactionCompletedEvent` (or `TransactionSuccessEvent`). The webhook engine **subscribes** to that event, completely decoupled from the UI.

---

### Phase 0: Event Completeness (Prerequisite)
The Ledger context currently publishes `TransactionFailedEvent` and `TransactionRefundedEvent`, but **no** `TransactionCompletedEvent`. We must add one.

**What we will build:**
- A `TransactionCompletedEvent` in `src/ledger/domain/events/`.
- Update the Ledger handler that completes a transaction (likely a `CompleteTransactionHandler`) to publish this event after success. (You already have manual admin actions; those actions should call a Ledger command like `CompleteTransactionCommand`, which then publishes the event.)

This ensures that all three webhook‑triggering events (`payment.completed`, `payment.failed`, `payment.refunded`) are emitted by the domain.

---

### Phase 1: Webhook Configuration (Merchant Aggregate Extension)
**Goal:** Attach webhook delivery details to the Merchant aggregate – but *only* from the Identity context. The configuration is part of the merchant’s identity, not the webhook engine.

**What we will build:**
- Add fields to the `merchants` table (via migration):
  - `webhook_url` TEXT (nullable)
  - `webhook_secret` TEXT (nullable)
  - `webhook_enabled` BOOLEAN (default 0)
- Extend the `Merchant` domain entity (in `src/identity/domain/`) with corresponding properties and maybe a Value Object for the URL (to enforce absolute URL).
- Create a `GenerateWebhookSecret` command/handler that generates a cryptographically secure secret, stores it, and displays it **once** (masked thereafter). This is a security requirement.
- Build a simple Admin UI (in the admin web layer) to manage these fields – this UI calls the Identity context’s application services.

---

### Phase 2: Outbox Pattern – The “Store” Part of Store‑and‑Forward
**Goal:** Prevent event loss. Since the current event bus is in‑memory and can lose events on crash, we must persist webhook jobs *atomically* with the business transaction. The outbox pattern is the canonical solution.

**What we will build:**
- **A new `webhook_outbox` table** in the same database, with columns:
  - `id` (auto‑increment or UUID)
  - `merchant_id`
  - `event_type` (e.g., `payment.completed`)
  - `payload` (JSON, the exact body to be sent)
  - `created_at`
  - `status` (pending / sent / failed)
  - `attempts` (integer)
  - `last_attempt_at`
  - `next_attempt_at` (for scheduling retries)
  - `signature` (pre‑calculated HMAC, so retries don’t regenerate)

- **A dedicated `WebhookOutboxRepository`** (infrastructure adapter) to persist and query outbox messages.

- **Event Handlers** that subscribe to the relevant domain events (`TransactionCompletedEvent`, `TransactionFailedEvent`, `TransactionRefundedEvent`). These handlers:
  1. Receive the domain event.
  2. Fetch the merchant’s webhook configuration (URL, secret, enabled) via an ACL to the Identity context.
  3. If webhooks are enabled for that merchant, build the exact JSON payload and compute the HMAC signature.
  4. Persist the outbox record *within the same UoW transaction* that the handler runs in. (The handlers are called after `uow.commit()` in the current architecture; we may need to move them **inside** the transaction. This is a small restructuring but essential for atomicity.)

**Important:** The outbox record is the **source of truth** for pending webhooks. No background job is created until the business transaction commits.

---

### Phase 3: The Forwarder – Background Worker
**Goal:** Process the outbox without blocking the main request thread.

**What we will build:**
- A **standalone worker process** (e.g., a Python script or a Flask CLI command) that runs a loop:
  1. Query `webhook_outbox` for records with `status = 'pending'` and `next_attempt_at <= now()`.
  2. For each record, send an HTTP POST to the merchant’s `webhook_url` with headers:
     - `Content-Type: application/json`
     - `X-Paymenter-Signature: sha256=<signature>`
     - `X-Paymenter-Event: <event_type>`
     - `X-Paymenter-Delivery: <outbox_id>`
  3. On successful response (2xx), mark the record as `sent`, increment attempts, and delete or archive.
  4. On failure, increment attempts, calculate next attempt time using **exponential backoff** (e.g., 1min, 5min, 30min, 1h, 2h), and update `next_attempt_at`. After a maximum number of attempts (e.g., 5), mark as `failed` and stop retrying.

- **Retry Policy** is defined as a Domain Service (pure logic) that calculates the next attempt time, keeping the worker free of complex rules.

- The worker runs in a separate thread within the Flask development server (for simplicity) or as a separate process in production. We’ll provide a `flask webhook-worker` CLI command.

---

### Phase 4: Observability – Audit Logs & Dashboard
**Goal:** See delivery status without querying the outbox table manually.

- **`webhook_delivery_logs` table** (or reuse outbox with status) – already covered by the outbox.
- **Admin UI page** that queries the outbox for recent deliveries, colour‑coded by status.
- **Manual Retry** button: sets the outbox record back to `pending` and resets `next_attempt_at` to `now()`.

---

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
