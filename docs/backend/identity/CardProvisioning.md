# MODULE DOCUMENTATION: CARD PROVISIONING
**Version:** 2.1.0

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
The Card Provisioning module is a reactive, event-driven sub-component of the Identity Bounded Context. Its sole responsibility is to listen for `AccountCreatedEvent` (originating from the Ledger context) and automatically issue a virtual payment card for the newly created account. It generates a 16-digit Luhn-valid Primary Account Number (PAN), persists it in the `user_cards` table using raw SQL within a Unit of Work, and emits a `CardAssignedEvent` to update downstream read models. This module operates strictly as a passive consumer with no external REST APIs, relying entirely on an in-memory synchronous event bus for cross-context communication.

---

## 2. Business Rules

### 1. Specification (WHAT)
*   **Trigger Mechanism:** Card provisioning is exclusively triggered by the `AccountCreatedEvent`, which carries `account_id` (UUID hex string), `user_id` (optional), `merchant_id` (optional), `account_number`, and `currency_code`.
*   **PAN Generation:** A 16-digit number is generated satisfying the Luhn checksum algorithm. The logic is implemented as a stateless utility function (`generate_card_number`) in the common infrastructure layer.
*   **Uniqueness Constraint:** The generated PAN must be globally unique. Uniqueness is enforced **solely at the database layer** via a `UNIQUE` constraint on the `user_cards.card_number` column. There is no application-level pre-check (`check_exists_func` is hardcoded to a no-op `lambda _: False`).
*   **Data Storage:** The raw 16-digit PAN is stored in plaintext in both `user_cards` and `user_summaries`.
*   **Ownership Linking:** The card is linked to either a `user_id` or a `merchant_id` and strictly tied to an `account_id` (UUID string).

### 2. Rationale & Trade-offs (WHY)
*   **Why Luhn validation?** Card numbers simulate real-world payment instruments. A Luhn-valid PAN ensures realistic behavior in integration testing and external gateway simulations.
*   **Why react to `AccountCreatedEvent`?** Strictly preserves Bounded Context isolation. Identity has no knowledge of Ledger's internal account creation logic; it only reacts to the fact that an account now exists.
*   **Why rely purely on DB constraints for uniqueness?** Given the 16-digit PAN space (with Luhn check digit), the probability of a collision is statistically negligible ($< 10^{-15}$). Skipping an application-level `SELECT` lookup avoids an extra database round-trip on every issuance, optimizing for MVP speed.
*   **Why Plaintext Storage?** Application-level encryption (e.g., AES-256) was rejected because it breaks the database's ability to enforce the `UNIQUE` constraint on the underlying PAN. Furthermore, the dashboard UI requires the plain card number for display. This is an acknowledged, deliberate deviation from PCI-DSS compliance for the sake of MVP delivery speed.
*   **Why Application-Layer UUIDs for `account_id`?** Generating the `account_id` as a UUID hex string in the application layer prior to persistence ensures that the identifier is deterministically known before the database transaction commits. This perfectly aligns with event-driven choreography, allowing the ID to be safely propagated through domain events without relying on database auto-increment return values.

### 3. Rejected Alternatives
*   **Rejected:** *Application-level uniqueness pre-check via Repository before insert.*
    *   **Reason:** Adds unnecessary latency and boilerplate for a collision probability that is practically zero. The database's `UNIQUE` constraint is the authoritative guardrail.
*   **Rejected:** *Implementing AES-256 encryption for the `card_number` column.*
    *   **Reason:** Reversible encryption adds key management complexity and hinders `UNIQUE` constraint enforcement. Hashing breaks the dashboard UI requirement. Deferred to the production migration phase.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)
*   **Application Layer (Handlers):**
    *   `OnAccountCreatedHandler`: Consumes `AccountCreatedEvent`, generates PAN, executes raw SQL `INSERT` via `self._uow.conn.execute()`, commits, and publishes `CardAssignedEvent`.
    *   `CardAssignedReadModelHandler`: Consumes `CardAssignedEvent`, executes raw SQL `UPDATE` on `user_summaries`.
*   **Domain Layer:**
    *   `CardAssignedEvent`: Dataclass containing `account_id: str`, `user_id: Optional[int]`, `merchant_id: Optional[int]`, and `card_number: str`.
    *   *Note:* No dedicated `Card` aggregate or `CardRepository` interface exists in the domain layer.
*   **Infrastructure Layer:**
    *   `generate_card_number`: Pure function in `src/common/infrastructure/generators.py`.
    *   `SqliteUnitOfWork`: Provides the `conn` (sqlite3.Connection) object used directly by handlers.
    *   `user_cards` table schema includes `account_id TEXT NOT NULL`, a `UNIQUE` constraint on `card_number`, and Foreign Keys to `users`, `merchants`, and `accounts(id)`.

### 2. Architectural Decisions (WHY)
*   **Why Raw SQL instead of the Repository Pattern?** The `user_cards` and `user_summaries` tables are treated as denormalized query models and simple side-effect logs, not domain aggregates. Creating a full `CardRepository` interface for a trivial `INSERT` violates the KISS principle and slows down MVP delivery. The raw SQL is strictly contained within the handler files.
*   **Why a free utility function instead of a Domain Service?** Card issuance is currently a pure, stateless operation depending only on randomness and the Luhn algorithm. Placing it in `common/infrastructure` keeps it reusable without over-engineering a `CardIssuanceService` domain service.
*   **Why reach into `uow.conn`?** It is a conscious MVP trade-off. While it leaks infrastructure concerns (SQLite) into the application layer, it avoids the boilerplate of a "Query Executor" abstraction. The schema is isolated, making future refactoring manageable.

### 3. Rejected Alternatives
*   **Rejected:** *Encapsulating PAN generation and persistence in a `CardIssuanceService` domain service.*
    *   **Reason:** Over-engineering for the MVP. The pure function and direct handler execution are sufficient and testable.
*   **Rejected:** *Creating a `CardRepository` interface in the domain layer.*
    *   **Reason:** The Constitution's Repository pattern is designed for aggregate persistence where business invariants must be enforced. Applying it to simple read-model projections contradicts KISS.

---

## 4. API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **Contract Type:** Passive Event Consumer (No REST/RPC endpoints).
*   **Subscribed Event:** `AccountCreatedEvent` (Published by Ledger Context).
    *   *Payload:* `account_id: str`, `user_id: Optional[int]`, `merchant_id: Optional[int]`, `account_number: AccountNumber`, `currency_code: CurrencyCode`.
*   **Published Event:** `CardAssignedEvent` (Consumed by Read Model Projections).
    *   *Payload:* `account_id: str`, `user_id: Optional[int]`, `merchant_id: Optional[int]`, `card_number: str`.
*   **Database Schema (`user_cards`):**
    ```sql
    CREATE TABLE IF NOT EXISTS user_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        merchant_id INTEGER,
        account_id TEXT NOT NULL, 
        card_number TEXT NOT NULL UNIQUE, 
        FOREIGN KEY (user_id) REFERENCES users(id), 
        FOREIGN KEY (merchant_id) REFERENCES merchants(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    );
    ```

### 2. Contract Choices (WHY)
*   **Why no REST endpoint to manually issue a card?** Card issuance is an automated, mandatory side-effect of account creation. Manual creation would bypass the invariant that every account gets exactly one card.
*   **Why carry both `user_id` and `merchant_id` instead of a polymorphic `owner_id`?** Explicit nullable fields make downstream SQL queries and event consumers simpler and strictly type-safe, avoiding the need for an `owner_type` discriminator column.
*   **Why an In-Memory Synchronous Bus?** The system is a modular monolith. An in-memory bus (`InMemoryEventBus`) was chosen for development speed, simplicity, and strict synchronous execution. The `EventBus` port allows swapping to RabbitMQ/Kafka later without changing domain logic.

### 3. Rejected Alternatives
*   **Rejected:** *Synchronous RPC (HTTP/gRPC) from Ledger to Identity.*
    *   **Reason:** Temporally couples the contexts. A failure in Identity would block account creation. Event-driven choreography allows independent availability.
*   **Rejected:** *Using an external Message Broker (RabbitMQ/Kafka) for the MVP.*
    *   **Reason:** Adds massive infrastructure and operational complexity for a single-process Flask application. Deferred until scaling requires asynchronous background workers.

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)
1.  **Trigger:** Ledger's `CreateAccountHandler` generates a UUID hex string for `account_id`, creates the Account aggregate, commits the new account to the DB, and publishes `AccountCreatedEvent` to the `InMemoryEventBus`.
2.  **Routing:** The synchronous bus routes the event to subscribers in the exact order they were registered in `identity_di.py`.
3.  **Read Model Update 1:** `AccountCreatedReadModelHandler` executes an `INSERT` or `UPDATE` on `user_summaries` to set the `account_id` and `balance`.
4.  **Card Provisioning:** `OnAccountCreatedHandler` receives the event.
    *   Validates that `user_id` or `merchant_id` is present.
    *   Calls `generate_card_number(lambda _: False)`.
    *   Executes raw SQL `INSERT` into `user_cards` via `uow.conn`, utilizing the string `account_id`.
    *   Commits the UoW transaction.
    *   Publishes `CardAssignedEvent`.
5.  **Read Model Update 2:** `CardAssignedReadModelHandler` receives `CardAssignedEvent` and executes an `UPDATE` on `user_summaries` to set the `card_number`.

### 2. Sequence Justification (WHY)
*   **Why this exact order?** The synchronous nature of the `InMemoryEventBus` guarantees that `AccountCreatedReadModelHandler` runs *before* `OnAccountCreatedHandler`. This ensures the `user_summaries` row exists before the card assignment handler attempts to `UPDATE` it.
*   **Why no Outbox Pattern or Idempotency Keys?** Because the bus is strictly synchronous and in-process, events are never reordered, dropped, or replayed. The mathematical guarantee of sequential execution eliminates the need for complex distributed systems patterns like the Transactional Outbox.
*   **Why early-exit if both owner IDs are None?** Defensive programming against malformed events, ensuring the handler doesn't crash on invalid foreign key insertions.

### 3. Rejected Alternatives
*   **Rejected:** *Updating `user_summaries` directly within the `OnAccountCreatedHandler`.*
    *   **Reason:** Blurs the boundary between Card Provisioning and Read Model modules, violating the Single Responsibility Principle.
*   **Rejected:** *Implementing an Outbox Pattern for event publishing.*
    *   **Reason:** Massive over-engineering for a synchronous modular monolith. The in-memory bus provides immediate consistency without the need for a polling publisher.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **PAN Collision (IntegrityError):** If `generate_card_number` produces a PAN that already exists in `user_cards`, the raw SQL `INSERT` fails.
*   **Uncaught Exception Bubble-up:** There is no `try-except` block catching `sqlite3.IntegrityError` in the handler.
*   **Plaintext PAN Leakage:** The database file (`paymenter.db`) contains raw, unencrypted 16-digit card numbers.

### 2. Root Cause & Impact (WHY)
*   **Why no error handling for collisions?** The probability of a 16-digit Luhn collision is $\approx 10^{-15}$. The team adopted a "fail-fast and fix later" mindset. 
*   **Impact of the Crash:** Because the bus is synchronous, the uncaught `IntegrityError` propagates up to the original Ledger `CreateAccountHandler`. This results in an HTTP 500 error to the client. The account remains created (if committed before publishing), but the user is left without a card, resulting in an inconsistent state and a broken dashboard UI.
*   **Why accept PCI-DSS non-compliance?** To avoid the performance hit of decryption on every read and the complexity of key management. The impact is that this codebase **cannot** be deployed to a real production environment processing real money without a complete security refactor.

### 3. Rejected Alternatives
*   **Rejected:** *Adding a `try-except` block with a retry loop (up to 3 times) on `IntegrityError`.*
    *   **Reason:** Adds code complexity and latency for a theoretical scenario that is statistically impossible at the MVP scale.
*   **Rejected:** *Using a deterministic encryption scheme (e.g., AES-SIV) to preserve uniqueness.*
    *   **Reason:** Too complex to implement and manage keys for the MVP phase.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Modular Monolith:** The entire system runs in a single Python/Flask process. Bounded contexts (Identity, Ledger) are separated by folders and domain rules, but share the same SQLite database and memory space.
*   **Infrastructure as a Plugin:** The `EventBus` and `UnitOfWork` are defined as ABCs in `common/domain/ports`. The current implementations (`InMemoryEventBus`, `SqliteUnitOfWork`) are injected via `DIContainer`.
*   **Application-Layer ID Generation:** The `account_id` is generated as a UUID hex string in the Application layer (`uuid.uuid4().hex`) rather than relying on database auto-increment, ensuring deterministic event payloads.
*   **No `CardNumber` Value Object:** The domain relies on a primitive `str` for the card number, violating the "Primitive Obsession Forbidden" rule, but compensated by the strict Luhn generation logic.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Why a Modular Monolith over Microservices?** The team size and MVP timeline do not justify the operational overhead of network partitions, distributed tracing, and separate databases. The modular structure allows extracting the Identity context into a microservice later if scaling demands it.
*   **Why skip the `CardNumber` Value Object?** Creating a Value Object requires mapping it through the Repository pattern. Since the team chose raw SQL for speed, a Value Object would just be an unused domain artifact. The decision prioritizes shipping speed over strict Domain-Driven Design purity.

### 3. Rejected Alternatives
*   **Rejected:** *Relying on Database Auto-Increment for `account_id`.*
    *   **Reason:** Requires a post-insert fetch to retrieve the generated ID before publishing the `AccountCreatedEvent`. This tightly couples the event publishing to the database transaction lifecycle and complicates the Unit of Work pattern. Generating the UUID in the application layer simplifies the event-driven architecture.
*   **Rejected:** *Using a Database Trigger to generate and insert cards automatically upon account creation.*
    *   **Reason:** Triggers are opaque, bypass domain events (`CardAssignedEvent`), and make the system impossible to test via standard Python unit/integration tests.
*   **Rejected:** *Strict adherence to the Repository Pattern for all database writes.*
    *   **Reason:** While architecturally pure, enforcing it for simple read-model projections and side-effect logs would drastically increase boilerplate and slow down the MVP delivery timeline.