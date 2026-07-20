# CHECKOUT MODULE DOCUMENTATION

**Version:** 1.0.0

---

## Table of Contents
1. Overview
2. Business Rules
3. Backend Architecture
4. API Contract / Integration
5. Execution Flows
6. Edge Cases & Known Issues
7. Architectural Notes & Rejected Decisions

---

## 1. Overview
The Checkout module acts as the primary orchestration layer for the payment gateway within the Paymenter Modular Monolith. It bridges external merchants (via M2M APIs), end-users (via the hosted Gateway UI), and internal Bounded Contexts (Identity and Ledger). It is strictly responsible for session lifecycle management, secure OTP generation/verification, and the synchronous reservation of funds, adhering rigorously to Domain-Driven Design (DDD) and Hexagonal Architecture principles.

---

## 2. Business Rules

### 1. Specification (WHAT)
*   **State Machine Enforcement:** A `PaymentSession` aggregate strictly follows the state transitions: `Initiated` $\rightarrow$ `Authorized` | `Failed`. Any attempt to mutate a session outside this state machine raises a `PaymentSessionStateError`.
*   **OTP Card Binding:** An OTP is cryptographically and logically locked to the specific `CardNumber` used during the request. It has a strict 3-minute Time-To-Live (TTL).
*   **Card Match Validation:** The card presented during the `/authorize` step must exactly match the `otp_locked_card` stored in the session.
*   **Strict Value Objects (Rule 3 Compliance):** 
    *   `Money`: Encapsulates `Decimal` and `CurrencyCode`.
    *   `CardNumber`: Enforces 16-digit length and Luhn algorithm validation.
    *   `SessionToken`: Enforces the `gw_` prefix.
    *   `OtpCode`: Enforces 5-digit length and uses `secrets.compare_digest` for constant-time verification to prevent timing attacks.
    *   `CallbackUrl`: Enforces absolute URL formatting via `urllib.parse`.

### 2. Rationale & Trade-offs (WHY)
*   **Why OTP Card Binding?** Prevents session hijacking or Man-In-The-Middle (MITM) attacks where an attacker intercepts an OTP and attempts to apply it to a different, compromised card. It cryptographically proves physical possession of the specific card at the exact time of authorization.
*   **Why Strict Value Objects?** Enforces Constitution Rule 3 (Primitive Obsession). By pushing validation (Luhn, URL parsing) into the Value Object constructors, the Domain layer guarantees that no invalid state can ever exist within the `PaymentSession` aggregate. The Application layer cannot pass raw strings across boundaries.
*   **Why State Machine?** Prevents double-charging and ensures that a session cannot be authorized if it has already failed or been refunded, protecting the Ledger from invalid fund reservation requests.

### 3. Rejected Alternatives
*   **Alternative:** *Stateless OTP (Email/SMS only).* 
    *   **Reason for Rejection:** Sending an OTP to an email/phone without binding it to the specific card number removes the "physical possession" proof. If an attacker compromises the user's communication channel, they could authorize transactions on any card. Binding the OTP to the card number was chosen to maximize security and enforce strict invariant protection.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)
*   **Hexagonal/Clean Architecture:** Strict adherence to the Dependency Rule. The Domain layer has zero infrastructure imports.
*   **Database Schema (`gateway_sessions`):**
    *   `amount`: Stored as `TEXT` (e.g., `"100.00"`).
    *   `currency_id`: `TEXT` (References `currencies.id`).
    *   `merchant_id`: `INTEGER` (References `merchants.id`).
    *   `transaction_id`: `TEXT` (References `transactions.id`).
*   **Cross-Context Adapters (ACL):** 
    *   `LedgerFundReservationAdapter`: Injects the Ledger's `HoldFundsHandler` directly via the DI Container.
    *   `IdentityAccountLookupAdapter`: Queries the Identity context's database tables via the shared SQLite Unit of Work.
*   **Unit of Work:** `SqliteUnitOfWork` utilizes `PRAGMA journal_mode=WAL;` and supports nested transactions via a `_nesting_level` counter to ensure ACID compliance across context boundaries.

### 2. Rationale & Trade-offs (WHY)
*   **Why store `amount` as TEXT?** Checkout does not perform arithmetic on the amount; it merely passes it to the Ledger. Storing it as `TEXT` preserves the exact `Decimal` string representation provided by the merchant, avoiding SQLite's `REAL` (float) approximation issues. The Ledger handles the authoritative conversion to integer cents.
*   **Why synchronous Handler injection (Rule 5 Adaptation)?** Payment authorization is a blocking, request-response operation. By injecting the Ledger's Handler directly into the Checkout Adapter, the system eliminates network latency and leverages the shared Unit of Work to guarantee atomicity. If the Ledger hold fails, the entire Checkout transaction rolls back automatically.
*   **Why In-Memory Event Bus?** For a single-process Modular Monolith, a synchronous in-memory bus eliminates the operational overhead of external message brokers while strictly adhering to the `EventBus` port interface, allowing future replacement with Kafka/RabbitMQ without altering the Domain.

### 3. Rejected Alternatives
*   **Alternative:** *Storing `amount` as INTEGER (cents) in Checkout.* 
    *   **Reason for Rejection:** Checkout acts as a pass-through gateway. Converting the merchant's decimal string to integer cents prematurely in the Checkout context risks rounding errors before the Ledger's authoritative accounting logic processes it. TEXT preservation was chosen for absolute exactness.

---

## 4. API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **`POST /api/pay`** (Merchant M2M)
    *   *Success (200):* `{"token": "gw_...", "payment_url": "https://...", "status": "Awaiting User Authorization"}`
    *   *Failure (400):* `{"error": "<DomainException message>"}`
*   **`POST /api/refund`** (Merchant M2M)
    *   *Success (200):* `{"transaction_id": "<id>", "status": "Refunded/Failed"}`
*   **`GET /api/verify/<transaction_id>`** (Merchant M2M)
    *   *Success (200):* `{"transaction_id": <int>, "amount": "<Decimal>", "currency_code": "<str>", "status": "<str>"}`
*   **`GET /gateway/<token>`** (User H2M)
    *   Renders server-side HTML (`gateway.html`).
*   **`POST /gateway/request-otp`** (User AJAX)
    *   *Payload:* `{"token": "...", "card_number": "..."}`
    *   *Success (200):* `{"success": true, "expires_in": 180}`
*   **`POST /gateway/authorize`** (User Form Submit)
    *   *Fields:* `token` (hidden), `card_number`, `otp_code`.
    *   *Action:* 302 Redirect to `callback_url` with `transaction_id` and `gateway_status` appended as query parameters.

### 2. Rationale & Trade-offs (WHY)
*   **Why separate `/api` and `/gateway` blueprints?** Machine-to-Machine (M2M) communication requires stateless JSON APIs with API Key authentication. Human-to-Machine (H2M) requires token-based HTML rendering and form submissions. Mixing them violates the Single Responsibility Principle of the controllers and complicates middleware application.
*   **Why HTTP Redirect on `/authorize`?** Standard payment gateway UX relies on HTTP redirects to return the user to the merchant's site. Returning JSON would force the merchant to build complex frontend logic to handle the post-payment redirect, violating the principle of providing a seamless integration experience.

### 3. Rejected Alternatives
*   **Alternative:** *Single Page Application (SPA) using React/Vue for the Gateway.*
    *   **Reason for Rejection:** Rejected in favor of Flask server-side rendering (`render_template`). An SPA would require a frontend build pipeline, state management, and complex CORS handling. SSR was chosen for zero-config deployment, superior accessibility, and elimination of client-side routing vulnerabilities.

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)
1.  **Initiation:** Merchant calls `/api/pay`. Handler generates `gw_` token, saves session to DB, and publishes `PaymentInitiatedEvent` using **primitives** (`str`, `Decimal`).
2.  **OTP Request:** User enters card on Gateway UI. AJAX calls `/gateway/request-otp`. Handler verifies card exists in Identity context, generates 5-digit OTP, locks it to the card, sets 3-min expiry, and publishes `OtpRequestedEvent` using **Value Objects**.
3.  **Authorization:** User submits form to `/gateway/authorize`. Handler validates state, card match, and OTP. It synchronously calls the Ledger's `HoldFundsHandler` via the ACL. Upon success, it attaches the `transaction_id` to the session and redirects the user.

### 2. Rationale & Trade-offs (WHY)
*   **Why primitives in `PaymentInitiatedEvent`?** To prevent the consuming Notification context from importing `src.checkout.domain.value_objects`. Using primitives acts as a plain DTO, preserving strict Bounded Context isolation and preventing circular or inward-pointing dependency violations (Constitution Rule 1).
*   **Why synchronous Ledger call in Authorization?** The user is actively waiting on the HTTP request. An asynchronous flow would leave the user staring at a loading screen while the system waits for an event callback, destroying the gateway UX and requiring complex polling mechanisms.

### 3. Rejected Alternatives
*   **Alternative:** *Two-Phase Commit (2PC) or Saga Pattern for Authorization.*
    *   **Reason for Rejection:** Implementing a Saga with compensating transactions introduces massive architectural complexity. Because this is a modular monolith sharing a single SQLite database with ACID guarantees via the Unit of Work, a simple synchronous call inside the UoW is sufficient, highly performant, and vastly simpler to maintain.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **Event Loss on Crash (Outbox Problem):** If the application process crashes immediately after `uow.commit()` but before `event_bus.publish()`, the Domain Event is permanently lost.
*   **Idempotency Volatility:** The `@idempotent` decorator uses a global in-memory Python dictionary (`_idempotency_store`). State is lost on restart and not shared across multiple Gunicorn/uWSGI workers.
*   **Insecure Common Generators:** `common/infrastructure/generators.py` uses the predictable `random` module for OTPs and Card Numbers, while the Checkout context uses the secure `secrets` module.

### 2. Rationale & Trade-offs (WHY)
*   **Event Loss (Root Cause & Impact):** Caused by the deliberate omission of a Transactional Outbox pattern to maintain a zero-infrastructure footprint. *Impact:* Notifications might fail to send if a hard crash occurs in the microsecond window between DB commit and event dispatch. The `EventBus` port remains intact to allow future Outbox implementation without domain refactoring.
*   **Idempotency (Root Cause & Impact):** Implemented as an in-memory store to support single-instance deployments without external dependencies. *Impact:* If deployed in a clustered topology, duplicate requests hitting different workers will bypass idempotency checks. Production clustering requires swapping the store backend to Redis.
*   **Generators (Root Cause & Impact):** The common generators use `random` strictly for test data seeding and fixture generation. *Impact:* Risk of accidental injection into production handlers. This is mitigated by the DI container explicitly wiring the `Secure` variants for all application handlers.

### 3. Rejected Alternatives
*   **Alternative:** *Database-backed Outbox and Idempotency Tables.*
    *   **Reason for Rejection:** Writing to outbox/idempotency tables on every single API call adds significant database write latency and I/O overhead. The in-memory implementations were chosen to maximize throughput and maintain a zero-dependency deployment topology, accepting the clustering constraints as a known architectural boundary.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Modular Monolith Topology:** The system runs as a single Python process with logically separated Bounded Contexts.
*   **In-Process ACL:** Cross-context communication is achieved by injecting the target context's Application Handler directly into the calling context's Infrastructure Adapter.
*   **SQLite with WAL:** The database uses Write-Ahead Logging to allow concurrent reads while writing, ensuring high throughput for a single-node deployment.

### 2. Rationale & Trade-offs (WHY)
*   **Why Modular Monolith over Microservices?** Microservices introduce network latency, distributed tracing requirements, and the complexity of distributed transactions (CAP theorem). A modular monolith provides the logical separation of DDD without the operational overhead of Kubernetes, service meshes, and network ACLs.
*   **Why SQLite over PostgreSQL?** PostgreSQL requires a dedicated database server, connection pooling, and infrastructure management. SQLite provides zero-config, file-based deployment, allowing the engineering team to focus purely on domain logic and business rules while maintaining strict ACID compliance.

### 3. Rejected Alternatives
*   **Alternative:** *HTTP/REST Anti-Corruption Layer between Checkout and Ledger.*
    *   **Reason for Rejection:** Even within a monolith, making HTTP calls between contexts introduces network serialization/deserialization overhead, timeout handling, and retry logic. Direct in-process Handler injection was chosen because it is significantly faster, type-safe, and leverages the shared Unit of Work for atomicity across bounded contexts.