### 📜 Eventing & Cross-Context Integration Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Cross-Context Integration](#backend-architecture--cross-context-integration)
   - [DI Container](#di-container)
   - [Event Bus](#event-bus)
3. [Domain Events Reference](#domain-events-reference)
4. [Edge Cases & Known Issues](#edge-cases--known-issues)
5. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Eventing & Cross-Context Integration** module defines how the Ledger bounded context communicates with other contexts (specifically Notifications) through domain events. It ensures guaranteed delivery, strict boundary encapsulation, and asynchronous side-effect execution.

### Core Responsibilities
- **Event Publishing**: Delivering `TransactionCompletedEvent`, `TransactionFailedEvent`, and `TransactionRefundedEvent` via a persistent Outbox pattern.
- **Cross-Context Communication**: Ledger never directly calls other contexts; all communication is strictly via the EventBus.
- **Dependency Wiring**: The `DIContainer` serves as the single point for registering event subscriptions and resolving the EventBus singleton.
- **Notification Triggering**: `ReceiptEmailHandler` sends idempotent email receipts by delegating to `SmtpAdapter`.
- **Resilience**: Handles transient failures via exponential backoff and routes unresolvable messages to a Dead-Letter Queue (DLQ).

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 3: No Primitive Obsession | ✅ Enforced. Events strictly use `Money` Value Object. |
| Rule 5: Cross-Context via Events | ✅ Enforced. Ledger only communicates via EventBus. |
| Rule 1: Dependency Inward | ✅ EventBus, Outbox, and Handlers depend on abstractions (Ports). |
| Rule 2: New Feature = New File | ✅ Enforced. Outbox, Idempotency, and Schema refactoring done via new files. |
| Rule 6: Infrastructure as Plugin | ✅ Outbox, InMemoryEventBus, and SmtpAdapter are infrastructure details. |
| Rule 7: Schema Isolation | ✅ Enforced. DB schemas isolated by Bounded Context. |

---

## Backend Architecture — Cross-Context Integration

### DI Container
**File**: `app/di_container.py` & `app/di/ledger_di.py`

```
DIContainer
├── event_bus: OutboxEventBusDecorator (singleton, wraps InMemoryEventBus)
│   ├── Inner Bus: InMemoryEventBus
│   └── Worker: OutboxRelayWorker (Background Thread)
└── Subscriptions (Bound in notifications_di.py):
    ├── TransactionCompletedEvent → ReceiptEmailHandler.handle_completed
    ├── TransactionFailedEvent    → ReceiptEmailHandler.handle_failed
    ├── TransactionRefundedEvent  → ReceiptEmailHandler.handle_refunded
    └── PaymentInitiatedEvent     → ReceiptEmailHandler.handle_initiated
```

**Notes**:
- The `event_bus` is registered as a singleton and dynamically wrapped by `OutboxEventBusDecorator` during `ledger_di` registration to ensure resiliency.
- Subscriptions are wired at application startup to the inner bus.

### Event Bus
**Implementation**: `OutboxEventBusDecorator` + `InMemoryEventBus`

- **Type**: Asynchronous, persistent Outbox with in-memory dispatch via background daemon thread.
- **Publishing Rule**: Events are published **after** Unit of Work commit. However, instead of direct in-memory dispatch, the event payload is serialized and inserted into an `outbox_messages` table. A background `OutboxRelayWorker` picks up pending messages and publishes them to the inner `InMemoryEventBus`.
- **Failure Handling**: 
  - If the outbox DB insert fails, the exception propagates (preventing silent data loss).
  - If the inner bus handler (e.g., SMTP) fails, the worker catches the exception, increments the `retry_count`, and schedules it for the next cycle.
  - After 3 failures, the message status is set to `DEAD_LETTER` for manual inspection. It will no longer be retried automatically.

**Subscribed Handlers**:
- `ReceiptEmailHandler.handle_completed(TransactionCompletedEvent)`
- `ReceiptEmailHandler.handle_failed(TransactionFailedEvent)`
- `ReceiptEmailHandler.handle_refunded(TransactionRefundedEvent)`
- `ReceiptEmailHandler.handle_initiated(PaymentInitiatedEvent)` — Originates from the Checkout context.

**ReceiptEmailHandler**:
- Receives the event, extracts `user_email`, `amount` (as `Money` VO), `merchant_id`.
- Checks `IdempotencyPort` to ensure this event has not been processed before.
- Delegates to `SmtpAdapter.send()` for actual email delivery.
- Marks event as processed in `IdempotencyPort` upon success.

---

## Domain Events Reference

All events are frozen dataclasses defined in `src/ledger/domain/events/`. They are prepared inside the Unit of Work by handlers but published after `uow.commit()`.

| Event | Fields | Emitted By |
|---|---|---|
| `TransactionCompletedEvent` | `transaction_id`, `user_email`, `amount: Money`, `merchant_id` | `CompleteFundsHandler` (after UoW commit) |
| `TransactionFailedEvent` | Same fields | `FailAndRefundHandler` (when Pending → Failed) |
| `TransactionRefundedEvent` | Same fields | `FailAndRefundHandler` (when Success → Refunded) |

**Publishing Rule**: Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). The `OutboxEventBusDecorator` intercepts this external publish call to guarantee persistence prior to HTTP response return.

---

## Edge Cases & Known Issues

### EC-3: Phantom Events on Rollback
**Scenario**: An exception occurs inside `CompleteFundsHandler` after `uow.commit()` but before event publishing.
**Previous Behavior**: The transaction was committed, but the event was permanently lost.
**Current Behavior**: **RESOLVED**. The `OutboxEventBusDecorator` immediately persists the event to the `outbox_messages` table synchronously before returning the HTTP response. Even if the application crashes microseconds later, the background `OutboxRelayWorker` will safely dispatch the event upon application restart.
**Status**: ✅ Resolved via Approximate ACID Outbox Pattern.

### EC-4: Transaction ID Zero in Events
**Scenario**: A newly created transaction emits an event lacking its database-generated ID.
**Previous Behavior**: `SqliteTransactionRepository.add()` returned `lastrowid` but failed to hydrate the aggregate, leaving `id=0`.
**Current Behavior**: **RESOLVED**. `SqliteTransactionRepository.add()` now explicitly assigns `transaction.id = cursor.lastrowid` before yielding control back to the application layer. The Aggregate Root is never in a transient state post-persistence.
**Status**: ✅ Resolved via Infrastructure hydration fix.

---

## Notes & Technical Debt

- **TD-3 (Transaction ID Assignment Bug)**: **RESOLVED**. Aggregate hydration implemented in `sqlite_transaction_repository.py`.
- **TD-9 (Incomplete DI Wiring)**: **RESOLVED**. The `OutboxEventBusDecorator` provides a deterministic, automated wrapper around the base `InMemoryEventBus` during context DI registration, ensuring all published events are intercepted for persistence without manual per-handler wiring.
- **Future Consideration (True Distributed Outbox)**: The current outbox uses an independent, fast SQLite connection. In a distributed database environment (e.g., Postgres across microservices), this would be upgraded to a Postgres CTE inserting into both the business table and outbox table within the exact same shared transaction/connection.