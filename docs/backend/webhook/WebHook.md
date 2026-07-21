
# WebHook Module: Single Source of Truth (SSOT)

**Version:** 1.0.0

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules](#2-business-rules)
3. [Backend Architecture](#3-backend-architecture)
4. [API Contract / Integration](#4-api-contract--integration)
5. [Execution Flows](#5-execution-flows)
6. [Edge Cases & Known Issues](#6-edge-cases--known-issues)
7. [Architectural Notes & Rejected Decisions](#7-architectural-notes--rejected-decisions)

---

### Overview
The WebHook module asynchronously notifies external merchants of critical payment lifecycle events (completion, failure, refund). It implements a strict **Transactional Outbox Pattern** using a SQLite-backed queue, ambient database transactions via Python `contextvars`, and a standalone polling background worker. Payloads are secured using HMAC-SHA256 signatures to guarantee integrity and authenticity.

---

### Business Rules

#### 1. Specification (WHAT)
*   **Trigger Events:** Deliveries are triggered exclusively by `TransactionCompletedEvent`, `TransactionFailedEvent`, and `TransactionRefundedEvent`.
*   **Eligibility Invariant:** A delivery is queued only if the merchant has `webhook_enabled = True`, a valid `webhook_url`, and a `webhook_secret`.
*   **Payload Serialization:** The `amount` field is strictly serialized as a **String with 2 decimal places** (e.g., `"150.00"`). The `transaction_id` is a **32-character UUID hex string**.
*   **Cryptographic Signing:** Payloads are signed using HMAC-SHA256 with the merchant's `webhook_secret`.
*   **Automatic Retry Policy:** Maximum 5 attempts with hardcoded backoff intervals: `[1m, 5m, 30m, 1h, 2h]`.
*   **Manual Retry Intervention:** Resets `attempts` to `0` and `next_attempt_at` to current UTC time.

#### 2. Rationale (WHY)
*   **Strict Decimal Serialization:** Eliminates floating-point precision loss in loosely-typed merchant systems (e.g., JavaScript) and ensures exact signature verification.
*   **Hardcoded Retry Intervals:** Provides a predictable exponential backoff curve without the overhead of database-driven configuration matrices.
*   **Manual Retry Reset:** Aligns with the admin UI mental model, expecting an immediate, fresh dispatch attempt bypassing lingering backoff delays.

#### 3. Rejected Alternatives
*   **Configurable Per-Merchant Retry Policies:** 
    *   *Rejected because:* Implementing a DB/UI-driven configuration matrix introduces unjustified complexity (validation, caching) for the current simulator scope.

---

### Backend Architecture

#### 1. Technical Details (WHAT)
*   **Domain Layer:** `WebhookRetryPolicy` (Static utility for backoff calculation).
*   **Application Layer:** `WebhookOutboxEventHandler` (Listens to Ledger events, builds/signs payloads, persists to outbox), `RetryWebhookDeliveryHandler` (Orchestrates manual retries).
*   **Infrastructure Layer:**
    *   `SqliteUnitOfWork`: Uses `contextvars` to support **ambient transactions**, allowing nested UoWs to share the same SQLite connection.
    *   `SqliteMerchantWebhookConfigAdapter`: Opens a **brand new SQLite connection** to read Identity context tables, bypassing the ambient UoW.
    *   `webhook_worker.py`: Standalone infinite loop daemon (`while True` with `time.sleep(10)`).

#### 2. Decisions (WHY)
*   **Ambient Transactions (ContextVars):** Publishing events *inside* the Ledger's UoW and sharing the connection via `contextvars` guarantees **strong consistency**. The outbox record is committed atomically with the transaction state change, eliminating "phantom webhooks."
*   **Cross-Context Connection Isolation:** The config adapter bypasses the ambient UoW to enforce **Bounded Context separation**. The Webhook context never holds locks or participates in Identity transactions, keeping the adapter stateless and usable by the worker (which lacks a merchant UoW).

#### 3. Rejected Alternatives
*   **Fire-and-Forget Event Publishing (Outside UoW):** 
    *   *Rejected because:* It would cause "Phantom Webhooks" (missing notifications if the process crashes between Ledger commit and Outbox write). We sacrificed decoupling to guarantee atomicity.
*   **Sharing Ambient UoW Connection for Config Reads:** 
    *   *Rejected because:* It would violate Bounded Context isolation, allowing the Webhook context to accidentally hold locks on Identity tables.

---

### API Contract / Integration

#### 1. Exact Endpoints/Schemas (WHAT)
*   **Outbound Webhook Payload (JSON):**
    ```json
    {
      "event": "payment.completed", 
      "transaction_id": "a1b2c3d4e5f6...", // 32-char UUID hex
      "merchant_id": 42,
      "amount": "150.00", // Strict 2-decimal string
      "currency": "USD"
    }
    ```
*   **Outbound HTTP Headers:**
    *   `Content-Type: application/json`
    *   `X-Paymenter-Signature: sha256=<hex_digest>`
    *   `X-Paymenter-Event: payment.completed`
    *   `X-Paymenter-Delivery: 987`
*   **Inbound Admin Endpoints:**
    *   `POST /dashboard/merchants/<id>/webhook/configure`
    *   `POST /dashboard/merchants/<id>/webhook/generate-secret` (Returns `whsec_<token>`)
    *   `POST /webhooks/retry/<id>`

#### 2. Contract Choices (WHY)
*   **HMAC-SHA256 Signature:** Industry standard for verifying payload integrity without complex asymmetric key exchanges.
*   **Unrecoverable Secret:** The secret is flashed exactly once upon generation (`secrets.token_urlsafe(32)`), mimicking real-world write-only security paradigms.

#### 3. Rejected Alternatives
*   **Timestamp-Based Replay Protection (`X-Paymenter-Timestamp`):** 
    *   *Rejected because:* It raises the barrier to entry for simulator integrations, as merchants would need to implement clock-skew tolerance and timestamp validation logic.

---

### Execution Flows

#### 1. Step-by-step Sequence (WHAT)
*   **Event Ingestion (Atomic):**
    1. `Ledger` completes transaction $\rightarrow$ opens `SqliteUnitOfWork`.
    2. Publishes `TransactionCompletedEvent` via `InMemoryEventBus`.
    3. `WebhookOutboxEventHandler` intercepts event, reuses the **ambient connection** (via `contextvars`), fetches merchant config (via separate connection), signs payload, and inserts into `webhook_outbox`.
    4. Top-level UoW commits $\rightarrow$ Ledger state and Outbox record are persisted atomically.
*   **Dispatch (Worker):**
    1. Worker wakes $\rightarrow$ opens UoW $\rightarrow$ queries `status='pending'`.
    2. Re-fetches merchant config (ensuring latest URL).
    3. Dispatches HTTP POST (10s timeout).
    4. Updates status (`mark_as_sent` or `record_retry`).

#### 2. Sequence Justification (WHY)
*   **Synchronous Ingestion:** Ensures the outbox record exists before the HTTP response is returned, providing immediate consistency for the UI and eliminating phantom events.
*   **Config Re-fetch at Dispatch:** Ensures that if a merchant updates their webhook URL while an event is pending, the delivery is routed to the new endpoint.

#### 3. Rejected Alternatives
*   **Asynchronous Post-Commit Hooks:** 
    *   *Rejected because:* Implementing robust post-commit hooks in Flask/SQLite requires complex thread management, contradicting the simplicity of the synchronous `InMemoryEventBus`.

---

### Edge Cases & Known Issues

#### 1. Specific Scenario (WHAT)
*   **SQLite Concurrency Race Conditions:** If an admin triggers a manual retry (`UPDATE`) exactly when the worker is processing the same row (`UPDATE`), SQLite will throw `OperationalError: database is locked`.
*   **Plain-Text Secret Storage:** `webhook_secret` is stored unencrypted in the `merchants` table.
*   **Audit Trail Destruction:** Manual retries reset `attempts = 0`, erasing the history of automated failures.

#### 2. Root Cause & Impact (WHY)
*   **Concurrency Flaws:** Root cause is the lack of `BEGIN IMMEDIATE` or optimistic locking in the worker/admin UoW. Impact: Transient 500 errors or missed retries under high contention.
*   **Security Flaws:** Root cause is deliberate simulator simplification. Impact: Fails PCI-DSS audits; secrets are vulnerable at rest.

#### 3. Rejected Alternatives
*   **`BEGIN IMMEDIATE` / Optimistic Locking:** 
    *   *Rejected because:* The "Zero Infrastructure" constraint and low collision probability make the added complexity of explicit locking or version columns unjustified for the current scale.

---

### Architectural Notes

#### 1. Current Implementation (WHAT)
*   **Constitution Violation (Rule 5):** The Webhook context executes raw SQL directly against the `merchants` table owned by the Identity context (`SqliteMerchantWebhookConfigAdapter`).
*   **Dependency Rule Friction:** Tightly coupled to the physical schema of the Identity database.

#### 2. Discarded Alternatives (WHY)
*   **Event-Driven Read Model Projection:** 
    *   *Rejected because:* Identity would need to publish `MerchantWebhookConfiguredEvent`, and Webhook would need to maintain a local `webhook_configs` table. This was rejected due to high implementation cost and the fact that direct SQL perfectly satisfies functional requirements while preserving development speed.

#### 3. Rejected Alternatives
*   **Anti-Corruption Layer (ACL) / Internal API:** 
    *   *Rejected because:* Creating a dedicated internal API endpoint for the Webhook context to fetch merchant configs was deemed over-engineering for the simulator, sacrificing strict Bounded Context isolation for absolute development speed.