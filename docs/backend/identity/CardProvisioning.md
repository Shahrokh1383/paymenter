# MODULE DOCUMENTATION: IDENTITY BOUNDED CONTEXT (CARD PROVISIONING & MERCHANT MANAGEMENT)
**Version:** 3.0.0

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules](#2-business-rules)
3. [Backend Architecture](#3-backend-architecture)
4. [API Contract / Integration](#4-api-contract--integration)
5. [Execution Flows](#5-execution-flows)
6. [Edge Cases & Known Issues](#6-edge-cases--known-issues)
7. [Architectural Notes & Rejected Decisions](#7-architectural-notes--rejected-decisions)

---

## 1. Overview
The Identity Bounded Context is a reactive, event-driven module responsible for managing user identities, merchant onboarding, and the automated provisioning of virtual payment cards. It operates as a passive consumer to the Ledger context, listening for `AccountCreatedEvent` to automatically issue Luhn-valid Primary Account Numbers (PANs). Additionally, it manages Merchant configurations, specifically the setup and secret generation for outbound Webhook integrations. 

The module generates cryptographically secure API keys and webhook secrets, persists domain aggregates and read models using an ambient Unit of Work pattern with raw SQL optimizations, and emits domain events to update downstream projections. It operates strictly via an in-memory synchronous event bus and command handlers, ensuring strict transactional consistency within the modular monolith.

---

## 2. Business Rules

### 1. Specification (WHAT)
*   **Card Provisioning Trigger:** Exclusively triggered by the `AccountCreatedEvent` (carrying `account_id`, `user_id`, `merchant_id`, `account_number`, and `currency_code`).
*   **PAN Generation:** A 16-digit number is generated satisfying the Luhn checksum algorithm. The logic is implemented as a stateless utility function (`generate_card_number`) utilizing non-cryptographic randomness for digit generation, finalized with a deterministic check digit.
*   **Uniqueness Constraint:** The generated PAN must be globally unique. Uniqueness is enforced **solely at the database layer** via a `UNIQUE` constraint on the `user_cards.card_number` column. Application-level pre-checks are intentionally omitted.
*   **Data Storage:** The raw 16-digit PAN is stored in plaintext in both `user_cards` and `user_summaries`.
*   **Merchant Webhook Configuration:** Merchants can configure outbound webhook URLs and toggle their enabled state via the `ConfigureWebhookCommand`. URL validity is strictly enforced by the `WebhookUrl` Value Object (requiring `http` or `https` schemes).
*   **Webhook Secret Generation:** Secrets are generated using cryptographically secure randomness (`secrets.token_urlsafe`), prefixed with `whsec_`, and must meet a minimum length requirement (>= 20 chars).
*   **API Key Generation:** Merchant API keys are generated using `secrets.token_urlsafe`, strictly matching the regex `^pay_[A-Za-z0-9\-_]{43}$`.

### 2. Rationale & Trade-offs (WHY)
*   **Why Luhn validation?** Ensures realistic behavior in integration testing and external payment gateway simulations, maintaining compatibility with standard financial instrument validation logic.
*   **Why rely purely on DB constraints for PAN uniqueness?** Given the 16-digit PAN space (with Luhn check digit), the probability of a collision is statistically negligible ($< 10^{-15}$). Skipping an application-level `SELECT` lookup eliminates an unnecessary database round-trip, optimizing for high-throughput insertion performance.
*   **Why Plaintext PAN Storage?** Application-level encryption (e.g., AES-256) complicates the database's ability to enforce the `UNIQUE` constraint without introducing deterministic encryption schemes (like AES-SIV). Furthermore, downstream read models require the plain card number for dashboard rendering. This is a deliberate architectural trade-off prioritizing query performance and schema simplicity, with Format-Preserving Encryption (FPE) scheduled for future security hardening phases.
*   **Why Plaintext Webhook Secrets?** Unlike user passwords, webhook secrets must be retained in plaintext (or reversibly encrypted) by the dispatching system. The platform requires the raw secret to generate HMAC-SHA256 signatures for outgoing webhook payloads. Hashing the secret would cryptographically prevent the system from signing payloads. Access to these secrets is strictly gated by application-level authorization and boundary controls.
*   **Why Application-Layer UUIDs for `account_id`?** Generating the `account_id` as a UUID hex string in the application layer prior to persistence ensures the identifier is deterministically known before the database transaction commits. This aligns perfectly with event-driven choreography, allowing the ID to be safely propagated through domain events without relying on database auto-increment return values.

### 3. Rejected Alternatives
*   **Rejected:** *Application-level uniqueness pre-check via Repository before PAN insert.*
    *   **Reason:** Adds unnecessary latency and I/O overhead for a collision probability that is practically zero. The database's `UNIQUE` constraint is the authoritative, performant guardrail.
*   **Rejected:** *Hashing Webhook Secrets in the Database.*
    *   **Reason:** Hashing destroys the system's ability to act as a webhook dispatcher. To sign outgoing HTTP payloads with HMAC, the raw secret is mathematically required at runtime.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)
*   **Application Layer (Handlers):**
    *   `OnAccountCreatedHandler`: Consumes `AccountCreatedEvent`, generates PAN, executes raw SQL `INSERT` via ambient `UnitOfWork`, commits, and publishes `CardAssignedEvent`.
    *   `ConfigureWebhookHandler` & `GenerateWebhookSecretHandler`: Process commands to mutate the `Merchant` aggregate, persist changes via the Repository, and publish respective domain events.
    *   **Read Model Handlers:** Dedicated handlers (`AccountCreatedReadModelHandler`, `MerchantWebhookConfiguredReadModelHandler`, etc.) execute raw SQL `UPDATE`/`INSERT` statements to maintain denormalized CQRS read models (`user_summaries`, `merchant_summaries`).
*   **Domain Layer:**
    *   **Aggregates/Entities:** `Merchant` (encapsulates webhook configuration invariants and state toggling).
    *   **Value Objects:** `WebhookUrl` (validates URL structure), `ApiKey` (enforces strict regex formatting), `AccountNumber`, `CurrencyCode`.
    *   **Events:** `CardAssignedEvent`, `MerchantOnboardedEvent`, `MerchantWebhookConfiguredEvent`, `MerchantWebhookSecretGeneratedEvent`.
*   **Infrastructure Layer:**
    *   `SqliteUnitOfWork`: Implements the Unit of Work pattern using Python's `contextvars` to support **ambient transactions**. This allows nested UoW contexts and ensures strict transaction boundaries without passing connection objects explicitly through the domain layer.
    *   `generators.py`: Pure functions for generating Luhn-valid PANs, API keys, and cryptographic secrets.

### 2. Architectural Decisions (WHY)
*   **Why Ambient Transactions via `contextvars`?** It elegantly solves the transaction boundary problem in event-driven architectures. When an event handler triggers another handler that requires a UoW, `contextvars` ensures they share the same underlying SQLite connection and transaction context, preventing deadlocks and ensuring atomic commits across the entire synchronous event chain.
*   **Why Raw SQL for Read Models instead of the Repository Pattern?** The `user_summaries` and `merchant_summaries` tables are strictly denormalized query models (CQRS read side). Creating full Repository interfaces for trivial `INSERT`/`UPDATE` projections violates the KISS principle and adds unnecessary object-relational mapping overhead. Raw SQL is strictly contained within dedicated Read Model Handlers.
*   **Why Value Objects for Webhook URLs and API Keys?** To enforce domain invariants at the boundary. The `WebhookUrl` Value Object guarantees that no invalid scheme (e.g., `ftp://`) or malformed URL can ever enter the domain state, preventing runtime errors during asynchronous webhook dispatching.

### 3. Rejected Alternatives
*   **Rejected:** *Passing `connection` objects explicitly through all handlers and services.*
    *   **Reason:** Leads to severe signature pollution and tight coupling to the infrastructure layer. `contextvars` provides a clean, Pythonic implementation of the Ambient Context pattern.
*   **Rejected:** *Using an ORM (e.g., SQLAlchemy) for Read Model projections.*
    *   **Reason:** ORMs introduce significant overhead for simple bulk updates and projections. Raw SQL provides deterministic performance and exact control over the query execution plan.

---

## 4. API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **Contract Type:** Passive Event Consumer & Command Processor (Internal Modular Monolith).
*   **Subscribed Events:** 
    *   `AccountCreatedEvent` (Published by Ledger Context).
*   **Published Events:** 
    *   `CardAssignedEvent`, `MerchantOnboardedEvent`, `MerchantActivatedEvent`, `MerchantDeactivatedEvent`, `MerchantWebhookConfiguredEvent`, `MerchantWebhookSecretGeneratedEvent`.
*   **Commands:**
    *   `ConfigureWebhookCommand(merchant_id: int, webhook_url: Optional[str], webhook_enabled: bool)`
    *   `GenerateWebhookSecretCommand(merchant_id: int)`
*   **Database Schema (`merchants` & `merchant_summaries`):**
    ```sql
    CREATE TABLE IF NOT EXISTS merchants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        api_key TEXT NOT NULL UNIQUE,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        webhook_url TEXT,
        webhook_secret TEXT,
        webhook_enabled BOOLEAN NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS merchant_summaries (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        api_key TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        webhook_url TEXT,
        webhook_enabled BOOLEAN NOT NULL DEFAULT 0
    );
    ```

### 2. Contract Choices (WHY)
*   **Why carry both `user_id` and `merchant_id` in events instead of a polymorphic `owner_id`?** Explicit nullable fields make downstream SQL queries, CQRS projections, and event consumers strictly type-safe and simpler to index, avoiding the need for an `owner_type` discriminator column and complex polymorphic SQL joins.
*   **Why an In-Memory Synchronous Bus?** The system operates as a modular monolith. An in-memory bus guarantees strict synchronous execution and immediate consistency. The `EventBus` port abstraction allows future migration to an asynchronous message broker (e.g., RabbitMQ/Kafka) without altering domain logic.

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)
**Flow A: Card Provisioning (Event-Driven)**
1.  **Trigger:** Ledger's `CreateAccountHandler` generates a UUID, commits the Account, and publishes `AccountCreatedEvent`.
2.  **Ambient Transaction Start:** The synchronous bus routes the event. `SqliteUnitOfWork` initializes an ambient transaction via `contextvars`.
3.  **Read Model Update 1:** `AccountCreatedReadModelHandler` updates `user_summaries`.
4.  **Card Provisioning:** `OnAccountCreatedHandler` receives the event, generates a Luhn-valid PAN, executes raw SQL `INSERT` into `user_cards` using the ambient connection, commits, and publishes `CardAssignedEvent`.
5.  **Read Model Update 2:** `CardAssignedReadModelHandler` updates `user_summaries` with the new `card_number`.

**Flow B: Webhook Configuration (Command-Driven)**
1.  **Trigger:** Delivery layer invokes `ConfigureWebhookHandler` with a `ConfigureWebhookCommand`.
2.  **Aggregate Mutation:** Handler loads the `Merchant` aggregate via `MerchantRepository`. The `Merchant.configure_webhook()` method enforces invariants (e.g., cannot enable without a valid URL) and updates the `WebhookUrl` Value Object.
3.  **Persistence:** The repository persists the updated state. The UoW commits the ambient transaction.
4.  **Event Publication:** Post-commit, the handler publishes `MerchantWebhookConfiguredEvent`.
5.  **Projection:** `MerchantWebhookConfiguredReadModelHandler` updates the `merchant_summaries` table via raw SQL.

### 2. Sequence Justification (WHY)
*   **Why Post-Commit Event Publication in Command Handlers?** Events are published *after* `self._uow.commit()` to guarantee that downstream event handlers only react to successfully persisted state changes. This prevents phantom events from triggering side effects if the database transaction fails.
*   **Why Ambient Transactions for Event Chains?** Because the event bus is synchronous, an event handler might trigger another handler that also requires a UoW. Ambient transactions ensure that all nested operations share the exact same database transaction, guaranteeing atomicity across the entire event chain.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **PAN Collision (IntegrityError):** If `generate_card_number` produces a PAN that already exists in `user_cards`, the raw SQL `INSERT` fails with a database constraint violation.
*   **Uncaught Exception Bubble-up:** The `OnAccountCreatedHandler` does not implement a `try-except` block for `sqlite3.IntegrityError`.
*   **Cascading Transaction Rollbacks:** If a downstream read model handler fails during the synchronous event chain, the ambient transaction rolls back, potentially undoing the primary aggregate creation if not carefully bounded.

### 2. Root Cause & Impact (WHY)
*   **Why no retry logic for PAN collisions?** The probability of a 16-digit Luhn collision is $\approx 10^{-15}$. Implementing a retry loop introduces unnecessary latency and code complexity for a statistically impossible scenario. The system relies on the database's `UNIQUE` constraint as the absolute source of truth. If a collision occurs, the exception bubbles up, resulting in an HTTP 500, which is an acceptable failure mode for a statistical anomaly.
*   **Impact of Synchronous Bus Failures:** Because the bus is strictly synchronous and in-process, an unhandled exception in *any* subscriber (e.g., a read model projection failing) will propagate up the call stack and abort the ambient transaction. This ensures strict data consistency (no orphaned projections) but requires rigorous error handling in all read model handlers to prevent blocking primary domain operations.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Modular Monolith:** The entire system runs in a single Python process. Bounded contexts (Identity, Ledger) are strictly separated by domain rules and folder structures, but share the same SQLite database and memory space.
*   **CQRS Read Models:** The architecture strictly separates the write model (Domain Aggregates persisted via Repositories) from the read model (Denormalized tables updated via raw SQL in dedicated event handlers).
*   **Infrastructure as a Plugin:** The `EventBus` and `UnitOfWork` are defined as ABCs in `common/domain/ports`. Implementations are injected via the DI Container, ensuring the domain layer remains completely independent of SQLite or specific event routing mechanisms.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Why a Modular Monolith over Microservices?** The current scale and team size do not justify the operational overhead of network partitions, distributed tracing, and eventual consistency complexities. The strict modular boundaries allow for seamless extraction into microservices in the future if scaling demands dictate it.
*   **Why skip the `CardNumber` Value Object?** Creating a Value Object requires mapping it through the Repository pattern. Since the architecture utilizes optimized raw SQL for high-throughput card insertion, a Value Object would introduce unnecessary mapping overhead without providing additional domain value beyond the generation phase.

### 3. Rejected Alternatives
*   **Rejected:** *Using Database Triggers for Read Model Projections.*
    *   **Reason:** Triggers are opaque, bypass domain events, and make the system impossible to test via standard Python unit/integration tests. Explicit event handlers provide clear, testable, and version-controlled projection logic.
*   **Rejected:** *Implementing the Transactional Outbox Pattern.*
    *   **Reason:** The use of ambient transactions via `contextvars` in a synchronous modular monolith guarantees immediate consistency without the need for a polling publisher or outbox table. The Outbox pattern is reserved for future asynchronous, distributed microservice extractions.