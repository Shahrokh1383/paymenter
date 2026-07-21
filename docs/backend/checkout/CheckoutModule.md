# CHECKOUT MODULE DOCUMENTATION

**Version:** 3.0.0

---

## Table of Contents
1. Overview
2. Business Rules & Invariants
3. Backend Architecture & Transactional Boundaries
4. Security & Cryptography
5. API Contract & Integration Topology
6. Execution Flows & Event Orchestration
7. Edge Cases & Error Handling
---

## 1. Overview
The Checkout module serves as the primary orchestration layer for the payment gateway. It bridges external merchants (via M2M APIs), end-users (via the hosted Gateway UI), and internal Bounded Contexts (Identity and Ledger). It is strictly responsible for session lifecycle management, cryptographic OTP generation/verification, and the synchronous, atomic reservation of funds. The module enforces strict Hexagonal Architecture boundaries, utilizing an Anti-Corruption Layer (ACL) to isolate the Checkout domain from the internal mechanics of the Ledger and Identity contexts.

---

## 2. Business Rules & Invariants

### 1. State Machine Enforcement
The `PaymentSession` aggregate enforces a strict, unidirectional state machine to prevent double-charging and ensure ledger consistency:
*   `Initiated` $\rightarrow$ `Authorized`: Triggered only upon successful OTP verification and successful fund reservation in the Ledger.
*   `Initiated` $\rightarrow$ `Failed`: Triggered if the Ledger rejects the fund hold (e.g., insufficient funds, account not found) or if OTP validation fails terminally.
*   `Authorized` $\rightarrow$ `Failed`: Triggered via the `/refund` API if the merchant requests a cancellation post-authorization.

### 2. OTP & Card Binding
*   **Physical Possession Proof:** An OTP is cryptographically and logically locked to the specific `CardNumber` used during the request.
*   **TTL Enforcement:** OTPs have a strict 3-minute Time-To-Live. Expiration is validated at the domain layer before any Ledger interaction occurs.
*   **Card Match Validation:** The card presented during the `/authorize` phase must exactly match the `otp_locked_card`.

### 3. Strict Value Objects (Primitive Obsession Prevention)
The Domain layer guarantees no invalid state can exist within the aggregate by pushing validation into Value Object constructors:
*   `Money`: Encapsulates `Decimal` (exact precision) and `CurrencyCode`.
*   `CardNumber`: Enforces 16-digit length and passes the Luhn algorithm check.
*   `SessionToken`: Enforces the `gw_` prefix and URL-safe entropy.
*   `OtpCode`: Enforces 5-digit length; verification uses constant-time comparison.
*   `CallbackUrl`: Enforces absolute URL formatting via `urllib.parse` (scheme + netloc required).
*   `WebhookUrl` (Identity Context): Enforces `http`/`https` schemes. The `Merchant` aggregate enforces the invariant: *A webhook cannot be enabled without a valid URL.*

---

## 3. Backend Architecture & Transactional Boundaries

### 1. Distributed Unit of Work (Cross-Context ACID)
To maintain strict ACID guarantees across Bounded Contexts without the overhead of Two-Phase Commit (2PC) or distributed Sagas, the architecture employs a **Shared Unit of Work** pattern:
*   **Transaction-Agnostic Handlers:** Ledger Application Handlers (`HoldFundsHandler`, `FailAndRefundHandler`) are strictly forbidden from calling `self._uow.commit()`. They only mutate domain state and register events.
*   **Orchestrator Commits:** The Checkout Application Handlers wrap the entire operation—including the cross-context ACL calls to the Ledger—inside a single `with self._uow:` block. If the Ledger raises an exception (e.g., `AccountNotFoundError`), the shared UoW rolls back both the Checkout session state and any partial Ledger mutations atomically.

### 2. Anti-Corruption Layer (ACL) & Direct Injection
*   **Adapter Pattern:** Checkout communicates with the Ledger via Port interfaces (`FundReservationPort`, `TransactionRefundPort`).
*   **Direct Handler Injection:** The ACL adapters (`LedgerFundReservationAdapter`) receive fully constructed Ledger Handlers via the DI Container. This avoids the serialization overhead and timeout complexities of HTTP/REST inter-context communication while maintaining runtime decoupling and leveraging the shared SQLite UoW for atomicity.

### 3. Database Schema Design
*   **`amount` as TEXT:** The `gateway_sessions` table stores the transaction amount as `TEXT`. Checkout acts as a pass-through orchestrator. Storing the exact `Decimal` string representation prevents SQLite `REAL` (float) approximation artifacts. The Ledger performs the authoritative numeric conversion and rounding logic.

---

## 4. Security & Cryptography

### 1. Entropy Generation
*   **Session Tokens:** Generated using `secrets.token_urlsafe(24)`, ensuring high-entropy, URL-safe, and unpredictable gateway URLs.
*   **OTP Codes:** Generated using `secrets.choice`, utilizing a Cryptographically Secure Pseudo-Random Number Generator (CSPRNG) to prevent offline prediction attacks.

### 2. Timing Attack Mitigation
*   OTP verification strictly utilizes `secrets.compare_digest(self.value, input_code)`. This ensures constant-time string comparison, neutralizing timing side-channel attacks that attempt to guess the OTP character-by-character.

### 3. Webhook Payload Security
*   Merchants configuring webhooks are issued a `webhook_secret` (minimum 20 characters). This secret is intended for HMAC-SHA256 signing of outbound event payloads, ensuring merchants can cryptographically verify that state-change notifications originated from the gateway and were not tampered with in transit.

---

## 5. API Contract & Integration Topology

### 1. Machine-to-Machine (M2M) Endpoints
*   **`POST /api/pay`**: Initiates a session. Requires `x-api-key`. Returns `token`, `payment_url`, and `status`.
*   **`POST /api/refund`**: Reverses a transaction. Takes `transaction_id`. Triggers the `FailAndRefundHandler` via ACL.
*   **`GET /api/verify/<transaction_id>`**: Queries the Ledger for the authoritative status of a transaction.

### 2. Human-to-Machine (H2M) Endpoints
*   **`GET /gateway/<token>`**: Renders the server-side hosted payment UI.
*   **`POST /gateway/request-otp`**: AJAX endpoint. Validates card ownership via Identity ACL, generates OTP, and mutates the aggregate.
*   **`POST /gateway/authorize`**: Form submission. Validates state/OTP, executes the cross-context fund hold, and issues an HTTP 302 Redirect to the merchant's `callback_url` with the `transaction_id` appended.

### 3. Blueprint Separation
M2M and H2M routes are isolated in separate Flask Blueprints (`api_bp`, `gateway_bp`). This enforces the Single Responsibility Principle (SRP), separating stateless JSON/API-Key authentication from HTML rendering and session-based form submissions.

---

## 6. Execution Flows & Event Orchestration

### 1. Authorization Sequence (Happy Path)
1.  **State Validation:** Handler loads `PaymentSession`, verifies `Initiated` state, checks OTP expiration, and validates Card Match.
2.  **Identity ACL:** Resolves the internal `account_id` for the provided Card Number and the Merchant's settlement account.
3.  **Ledger ACL (Synchronous):** Invokes `HoldFundsHandler` inside the shared UoW. Funds are moved to the Escrow account.
4.  **State Mutation:** Session transitions to `Authorized`, `transaction_id` is attached, and the UoW commits atomically.
5.  **Redirect:** User is redirected to the merchant's callback URL.

### 2. Domain Event Publishing Strategy
*   **Post-Commit Publishing:** Checkout events (`PaymentInitiatedEvent`, `OtpRequestedEvent`) are published *after* the UoW successfully commits. This guarantees that consumers only react to persisted, valid state changes.
*   **Payload Isolation:** `PaymentInitiatedEvent` uses primitive types (`str`, `Decimal`) to prevent downstream contexts (like Notification) from importing Checkout domain Value Objects, preserving strict Bounded Context isolation. Conversely, `OtpRequestedEvent` utilizes Value Objects for internal routing where kernel sharing is acceptable.

---

## 7. Edge Cases & Error Handling

### 1. Ledger Rejection & State Rollback
If the Ledger raises an exception (e.g., `AccountNotFoundError`, `InsufficientFundsError`) during the `hold_funds` ACL call:
*   The shared UoW intercepts the exception and triggers a database rollback.
*   The Checkout handler catches the exception, explicitly calls `session.mark_as_failed()`, and initiates a secondary, minimal UoW commit to persist the `Failed` state. This ensures the merchant can query the session and see a terminal failure state rather than a perpetual `Initiated` limbo.

### 2. Idempotency & Concurrency
*   **Session Uniqueness:** The `gw_` token generation includes a database-level existence check (`check_exists_func`) to guarantee uniqueness.
*   **Ledger Idempotency:** The Ledger's `/complete` and `/fail` endpoints utilize an in-memory idempotency cache to prevent duplicate processing from network retries. *(Note: For multi-node deployments, this cache must be upgraded to a distributed store like Redis).*