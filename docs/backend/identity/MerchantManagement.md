# MODULE DOCUMENTATION: MERCHANT MANAGEMENT & WEBHOOK INTEGRATION

**Version:** 3.1.0 (SSOT - Enterprise Architecture)  

## Table of Contents
1. [Overview](#overview)
2. [Business Rules & Invariants](#business-rules--invariants)
3. [Backend Architecture](#backend-architecture)
4. [API Contract & Integration](#api-contract--integration)
5. [Execution Flows](#execution-flows)
6. [Edge Cases & Resiliency Patterns](#edge-cases--resiliency-patterns)
7. [Architectural Notes & Design Rationale](#architectural-notes--design-rationale)

---

## Overview
The Merchant Management module governs the lifecycle of `Merchant` aggregates within the Identity bounded context. It handles onboarding, secure API key generation, state transitions, and external Webhook configuration. Operating as an internal administrative service, it utilizes a strict CQRS architecture with event-driven, isolated read-model projections. Merchants act as cross-context Account Owners within the `Ledger` bounded context, enabling them to hold balances and receive virtual cards. The Webhook subsystem allows merchants to configure secure, event-driven HTTP callbacks for external system integration.

---

## Business Rules & Invariants

### 1. Domain Invariants
*   **API Key Entropy:** Strictly `pay_` followed by exactly 43 URL-safe Base64 characters. Validated via regex `^pay_[A-Za-z0-9\-_]{43}$` within the immutable `ApiKey` Value Object.
*   **Webhook URL Validation:** The `WebhookUrl` Value Object enforces absolute URL formatting (`http` or `https` schemes) via `urllib.parse` to guarantee valid callback endpoints.
*   **Webhook State Invariant:** A webhook cannot be transitioned to an `enabled` state without a valid, non-null `WebhookUrl`. This invariant is strictly protected within the `Merchant.configure_webhook()` aggregate method to prevent invalid domain states.
*   **Webhook Secret Entropy:** Secrets are prefixed with `whsec_` followed by 32 bytes of cryptographically secure random data (`secrets.token_urlsafe`), yielding high-entropy tokens for HMAC signature verification. Minimum length enforcement is handled at the domain layer.
*   **State Machine:** The `is_active` boolean flag governs the merchant's operational state. Transitions are encapsulated within `Merchant.toggle()` to prevent an Anemic Domain Model.

### 2. Write Model Schema
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
```

---

## Backend Architecture

### 1. CQRS & Event-Driven Projections
*   **Isolated Read Model:** The `merchant_summaries` table is a denormalized projection. It intentionally omits `webhook_secret` to prevent sensitive credential leakage into UI-facing read models.
*   **No Foreign Key Coupling:** The read model lacks a `FOREIGN KEY` constraint to the write model. This enforces strict bounded context independence, allowing the read model to be dropped and rebuilt entirely from the event log without schema conflicts.
*   **Transactional Isolation:** Read-model projections execute in strictly isolated `UnitOfWork` instances. A projection failure will not cascade into a rollback of the core domain transaction, preserving write-side availability.

### 2. Read Model Schema
```sql
CREATE TABLE IF NOT EXISTS merchant_summaries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    webhook_url TEXT,
    webhook_enabled BOOLEAN NOT NULL DEFAULT 0
);
```

### 3. Domain Events
State changes emit immutable domain events to trigger asynchronous projections:
*   `MerchantOnboardedEvent`
*   `MerchantActivatedEvent` / `MerchantDeactivatedEvent`
*   `MerchantWebhookConfiguredEvent`
*   `MerchantWebhookSecretGeneratedEvent`

---

## API Contract & Integration

### 1. Administrative Endpoints
*   `POST /dashboard/merchants/add`: Triggers `OnboardMerchantCommand`.
*   `POST /dashboard/merchants/toggle/<id>`: Triggers `ToggleMerchantCommand`.
*   `POST /dashboard/merchants/<id>/webhook/configure`: Triggers `ConfigureWebhookCommand`.
*   `POST /dashboard/merchants/<id>/webhook/generate-secret`: Triggers `GenerateWebhookSecretCommand`.

### 2. Cross-Context Integration
Merchants are passed as `owner_type='merchant'` to the Ledger's `CreateAccountCommand`. The Identity context listens to Ledger's `AccountCreatedEvent` to project account summaries into the Identity read model, maintaining eventual consistency across bounded contexts.

### 3. Exception Handling & Security
*   **Domain Exceptions:** All aggregate invariant violations raise typed `DomainException` subclasses (e.g., `NotFoundError`, `InvariantViolationError`).
*   **Global Error Mapping:** A global Flask error handler intercepts `DomainException` and maps them to localized, user-friendly flash messages, strictly preventing internal stack trace or database schema leakage to the client.
*   **Secure Secret Handoff:** Webhook secrets are generated synchronously and handed off via an ephemeral, single-use cryptographic vault or secure UI rendering mechanism. Secrets are strictly excluded from read-model projections (`merchant_summaries`) to prevent unauthorized exposure.

---

## Execution Flows

### 1. Webhook Configuration Flow
1.  HTTP POST triggers `ConfigureWebhookCommand`.
2.  `ConfigureWebhookHandler` loads the `Merchant` aggregate within a Write `UnitOfWork`.
3.  `merchant.configure_webhook()` enforces domain invariants.
4.  The repository persists the state; the `UnitOfWork` commits.
5.  Post-commit, `MerchantWebhookConfiguredEvent` is published to the `EventBus`.
6.  `MerchantWebhookConfiguredReadModelHandler` catches the event, opens an *isolated* Read `UnitOfWork`, and updates the `merchant_summaries` projection.

### 2. Post-Commit Event Publishing
Events are strictly published *after* the database transaction commits. This guarantees that event subscribers never react to phantom entities that might be rolled back, eliminating read-your-own-writes inconsistencies and race conditions.

---

## Edge Cases & Resiliency Patterns

### 1. Eventual Consistency & Outbox Pattern
*   **Scenario:** The write transaction commits, but the read-model projection experiences an I/O fault.
*   **Resolution:** To guarantee delivery and prevent projection failures from rolling back core domain transactions, the system implements the **Transactional Outbox Pattern**. Events are persisted to an outbox table within the same ACID transaction as the write-model aggregate, ensuring zero message loss during asynchronous read-model hydration.

### 2. Optimistic Concurrency Control (OCC)
*   **Scenario:** Rapid, concurrent toggle or configuration requests.
*   **Resolution:** To prevent unintended state flips, command handlers implement OCC by verifying the aggregate's expected state (or version number) before applying mutations, throwing a `ConcurrencyException` if the state has drifted.

### 3. CQRS Boundary Enforcement
*   **Scenario:** Querying webhook status.
*   **Resolution:** The `MerchantRepository.get_webhook_status()` method strictly queries the Write Model (`merchants` table). Querying the Read Model from the Write-side repository is an architectural violation that introduces hidden coupling and stale data risks.

---

## Architectural Notes & Design Rationale

### 1. Pure Domain Value Objects
The `ApiKey` and `WebhookUrl` Value Objects strictly validate format but do not generate random strings or perform network I/O. Generation is delegated to the Infrastructure layer (`generators.py`, `secrets` module) to keep the Domain layer pure, deterministic, and easily testable.

### 2. Modular Dependency Injection
The `identity_di.py` module acts as an isolated wiring context for the Identity bounded context. It registers factory functions to the main `DIContainer` and subscribes handlers to the `EventBus` with isolated `UnitOfWork` instances. This prevents cross-context pollution and strictly adheres to the Dependency Inversion Principle.

### 3. In-Process Event Dispatching
The `EventBus` operates synchronously within the application process boundary. This enforces immediate read-model consistency for administrative workflows while preserving the strict Domain Event interface. This architectural seam allows seamless migration to an asynchronous, distributed message broker (e.g., Kafka, RabbitMQ) without altering domain or application layer contracts.