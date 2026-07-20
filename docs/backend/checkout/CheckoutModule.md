# CHECKOUT MODULE DOCUMENTATION

**Version:** 2.0.0

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
The Checkout module acts as the primary orchestration layer for the payment gateway within the Paymenter Modular Monolith. It bridges external merchants (via M2M APIs), end-users (via the hosted Gateway UI), and internal Bounded Contexts (Identity and Ledger). It is strictly responsible for session lifecycle management, secure OTP generation/verification, and the synchronous reservation of funds. It enforces Domain-Driven Design (DDD) and Hexagonal Architecture boundaries, though it currently harbors specific technical debt regarding DI container isolation and state machine rollback behaviors.

## 2. Business Rules 

### 1. Specification (WHAT) 
*   **State Machine Enforcement:** A `PaymentSession` aggregate strictly follows the state transitions: `Initiated` $\rightarrow$ `Authorized`. *(Note: Transition to `Failed` is currently unimplemented in the orchestration layer; ledger failures cause a rollback, not a state mutation).*
*   **OTP Card Binding:** An OTP is logically locked to the specific `CardNumber`. It has a strict 3-minute TTL.
*   **Card Match Validation:** The card presented during `/authorize` must exactly match the `otp_locked_card`.
*   **Strict Value Objects:** 
    *   `Money`: Encapsulates `Decimal` and `CurrencyCode`.
    *   `CardNumber`: Enforces 16-digit length and Luhn algorithm.
    *   `SessionToken`: Enforces `gw_` prefix.
    *   `OtpCode`: Enforces 5-digit length; uses `secrets.compare_digest`.
    *   `CallbackUrl`: Enforces absolute URL formatting via `urllib.parse`.

### 2. Rationale (WHY) 
*   **Why OTP Card Binding?** Prevents session hijacking. Cryptographically proves physical possession of the specific card at the exact time of authorization.
*   **Why Strict Value Objects?** Enforces Primitive Obsession prevention. By pushing validation into constructors, the Domain layer guarantees no invalid state can exist within the aggregate.
*   **Why State Machine?** Prevents double-charging and ensures the Ledger is not hit with invalid fund reservation requests.

### 3. Rejected Alternatives
*   **Alternative:** *Stateless OTP (Email/SMS only).* 
    *   **Reason for Rejection:** Sending an OTP without binding it to the card number removes the "physical possession" proof. If an attacker compromises the user's communication channel, they could authorize transactions on any card. Binding was chosen to maximize security.

## 3. Backend Architecture 

### 1. Technical Details (WHAT) 
*   **Hexagonal Architecture:** Strict adherence to the Dependency Rule. Domain has zero infrastructure imports.
*   **Database Schema (`gateway_sessions`):** `amount` stored as `TEXT`. `currency_id` and `merchant_id` as references.
*   **Cross-Context Adapters (ACL):** `LedgerFundReservationAdapter` injects the Ledger's `HoldFundsHandler` directly via the DI Container.
*   **Unit of Work:** `SqliteUnitOfWork` utilizes `PRAGMA journal_mode=WAL;` and supports nested transactions via a `_nesting_level` counter.

### 2. Decisions (WHY) 
*   **Why store `amount` as TEXT?** Checkout acts as a pass-through. Storing as `TEXT` preserves the exact `Decimal` string representation, avoiding SQLite `REAL` (float) approximation. The Ledger handles authoritative conversion.
*   **Why synchronous Handler injection?** Authorization is blocking. Injecting the Ledger's Handler directly eliminates network latency and leverages the shared Unit of Work to guarantee atomicity across bounded contexts.

### 3. Rejected Alternatives
*   **Alternative 1:** *Storing `amount` as INTEGER (cents) in Checkout.* 
    *   **Reason for Rejection:** Checkout is a pass-through. Premature conversion to integer cents risks rounding errors before the Ledger processes it. TEXT was chosen for exactness.
*   **Alternative 2:** *Formal Port Interface for Ledger instead of Direct Handler Injection.*
    *   **Reason for Rejection:** Strict DDD prefers a `LedgerPort` that the adapter calls to avoid compile-time dependencies between contexts. This was rejected in favor of **anti-corruption layer pragmatism**; injecting the handler avoids an extra abstraction layer that would merely delegate to the handler, keeping the codebase smaller at the cost of weaker bounded context isolation.

## 4. API Contract / Integration 

### 1. Exact Endpoints/Schemas (WHAT) 
*   **`POST /api/pay`** (Checkout M2M): Requires `x-api-key`. Returns `{"token", "payment_url", "status"}`. *(No Idempotency applied)*.
*   **`POST /api/refund`** (Checkout M2M): Takes `transaction_id`. Returns status. *(No Idempotency applied)*.
*   **`GET /api/verify/<transaction_id>`** (Checkout M2M): Returns transaction details. *(Warning: Returns `amount` as float)*.
*   **`POST /api/transactions/<id>/complete`** (Ledger M2M): Uses `@idempotent` decorator.
*   **`POST /api/transactions/<id>/fail`** (Ledger M2M): Uses `@idempotent` decorator.
*   **`GET /gateway/<token>`** (H2M): Renders `gateway.html`.
*   **`POST /gateway/request-otp`** (H2M): Takes JSON `token`, `card_number`.
*   **`POST /gateway/authorize`** (H2M): Form submit. 302 Redirects to `callback_url`.

### 2. Contract Choices (WHY) 
*   **Why separate Blueprints?** M2M requires stateless JSON/API Key auth. H2M requires HTML rendering and form submissions. Mixing them violates SRP.
*   **Why HTTP Redirect?** Standard gateway UX relies on redirects. Returning JSON forces merchants to build complex frontend polling logic.
*   **Why Ledger uses Idempotency but Checkout doesn't?** Ledger's `/complete` and `/fail` endpoints are highly sensitive to duplicate processing (e.g., double completion). Checkout's `/pay` endpoint relies on the uniqueness of the `gw_` token and database constraints to prevent duplicate sessions.

### 3. Rejected Alternatives
*   **Alternative:** *Single Page Application (SPA) using React/Vue for the Gateway.*
    *   **Reason for Rejection:** Rejected in favor of Flask server-side rendering. An SPA requires a frontend build pipeline, state management, and complex CORS handling. SSR was chosen for zero-config deployment and elimination of client-side routing vulnerabilities.

## 5. Execution Flows 

### 1. Step-by-step Sequence (WHAT) 
1.  **Initiation:** Merchant calls `/api/pay`. Handler saves session, commits UoW, then publishes `PaymentInitiatedEvent` using **primitives** (`str`, `Decimal`).
2.  **OTP Request:** User enters card. AJAX calls `/gateway/request-otp`. Handler verifies card via Identity ACL, generates OTP, mutates aggregate, commits UoW, then publishes `OtpRequestedEvent` using **Value Objects**.
3.  **Authorization:** User submits form. Handler validates state/card/OTP. Calls Ledger's `HoldFundsHandler` via ACL inside the UoW. Upon success, attaches `transaction_id` and redirects.

### 2. Sequence Justification (WHY) 
*   **Why primitives in `PaymentInitiatedEvent`?** Prevents the consuming Notification context from importing Checkout domain VOs, preserving strict Bounded Context isolation.
*   **Why synchronous Ledger call?** The user is actively waiting. An asynchronous flow would require complex polling mechanisms, destroying the gateway UX.

### 3. Rejected Alternatives
*   **Alternative 1:** *Two-Phase Commit (2PC) or Saga Pattern for Authorization.*
    *   **Reason for Rejection:** Introduces massive complexity. Because the monolith shares a single SQLite DB with ACID guarantees via the Unit of Work, a synchronous call inside the UoW is highly performant and vastly simpler.
*   **Alternative 2:** *Transactional Outbox Pattern for Event Publishing.*
    *   **Reason for Rejection:** Events are currently published *after* `uow.commit()`, accepting the Outbox Problem (event loss on crash). This was rejected for **development pragmatism**; the risk of process crash in the local simulator is negligible, and the outbox would slow down prototyping. The architecture accepts this failure mode for a zero-infrastructure footprint.

## 6. Edge Cases & Known Issues 

### 1. Specific Scenario (WHAT) 
*   **Event Loss on Crash:** If the app crashes between `uow.commit()` and `event_bus.publish()`, the Domain Event is lost.
*   **DI Container Fragmentation:** `gateway_controller.py` uses a global `DIContainer()` instead of `current_app.di_container`. This isolates the Gateway's `EventBus`.
*   **State Machine Rollback Gap:** If Ledger raises `AccountNotFoundError` during authorization, the UoW rolls back. The session remains `Initiated` instead of `Failed`.
*   **Float Precision Loss:** `LedgerVerificationAdapter` casts DB amounts to `float`.
*   **Idempotency Volatility in Ledger:** The `@idempotent` decorator uses a global Python dictionary (`_idempotency_store`). It protects Ledger endpoints but is volatile.
*   **Insecure Common Generators:** `common/infrastructure/generators.py` uses predictable `random` for OTPs/Cards.

### 2. Root Cause & Impact (WHY) 
*   **Event Loss:** Deliberate omission of Outbox to maintain zero-infrastructure.
*   **DI Fragmentation:** Architectural drift. Instantiating the container globally at the module level breaks the Flask app-context DI wiring. OTP events never reach the Notification context.
*   **Rollback Gap:** Missing state orchestration. The handler fails to catch Ledger exceptions to explicitly transition the aggregate to `Failed` in a separate transaction.
*   **Idempotency Volatility:** Implemented as an in-memory store to support single-instance local simulation without Redis. *Impact:* If the Flask app runs with multiple Gunicorn/uWSGI workers, or restarts, the cache is lost. A merchant retrying a Ledger `/complete` request might hit a different worker, bypassing the idempotency check.
*   **Generators:** Maintained for backward compatibility with non-critical DB seeding, violating the principle of least surprise.

### 3. Rejected Alternatives
*   **Alternative 1:** *Database-backed Outbox and Redis Idempotency Tables.*
    *   **Reason for Rejection:** Writing to outbox/idempotency tables on every API call adds significant DB write latency and requires external dependencies (Redis). In-memory implementations were chosen to maximize throughput and maintain a zero-dependency topology, accepting the clustering constraints and crash risks as known boundaries.
*   **Alternative 2:** *Catching Ledger Exceptions to Force `Failed` State.*
    *   **Reason for Rejection:** The team opted for strict ACID rollbacks. If the Ledger fails, the Checkout session shouldn't record a "Failed" transaction ID because no transaction was ever created. However, this sacrifices merchant observability, which is a known trade-off.

## 7. Architectural Notes 

### 1. Current Implementation (WHAT) 
*   **Modular Monolith Topology:** Single Python process, logically separated contexts.
*   **In-Process ACL:** Cross-context communication via direct Handler injection.
*   **Manual Auth Middleware:** The `api_controller` manually instantiates `SqliteUnitOfWork` and `SqliteMerchantRepository` to authenticate API keys.
*   **Execution Environment:** Requires `PYTHONPATH` to be set to the project root to resolve `src.common...` imports correctly when running `main.py`.

### 2. Discarded Alternatives (WHY) 
*   **Why Modular Monolith over Microservices?** Microservices introduce network latency, distributed tracing, and CAP theorem complexities. The monolith provides logical DDD separation without Kubernetes overhead.
*   **Why SQLite over PostgreSQL?** PostgreSQL requires dedicated servers and connection pooling. SQLite provides zero-config, file-based deployment, allowing focus purely on domain logic.

### 3. Rejected Alternatives
*   **Alternative 1:** *HTTP/REST Anti-Corruption Layer between Checkout and Ledger.*
    *   **Reason for Rejection:** HTTP calls introduce serialization overhead and timeout handling. Direct in-process injection is faster, type-safe, and leverages the shared UoW for atomicity.
*   **Alternative 2:** *Abstracted Auth Service injected via DI for Middleware.*
    *   **Reason for Rejection:** The manual SQLite instantiation in the `authenticate()` middleware violates the Dependency Rule. This was rejected initially for **speed of implementation**. Abstracting it into an injected Application Service would require additional ports and wiring; the team accepted this technical debt to deliver a functional middleware quickly, intending to refactor it later.