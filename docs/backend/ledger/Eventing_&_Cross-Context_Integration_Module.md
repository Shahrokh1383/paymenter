# Eventing & Cross-Context Integration Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

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

The **Eventing & Cross-Context Integration** module defines how the Ledger bounded context communicates with other contexts (specifically Notifications) through domain events. It includes the `InMemoryEventBus`, the global `DIContainer` that wires subscriptions, and the `ReceiptEmailHandler` that reacts to transaction lifecycle events.

### Core Responsibilities
- **Event Publishing**: Delivering `TransactionCompletedEvent`, `TransactionFailedEvent`, and `TransactionRefundedEvent` to subscribed handlers.
- **Cross-Context Communication**: Ledger never directly calls other contexts; all communication is via the EventBus.
- **Dependency Wiring**: The `DIContainer` serves as the single point for registering event subscriptions and resolving the EventBus singleton.
- **Notification Triggering**: `ReceiptEmailHandler` sends email receipts by delegating to `SmtpAdapter`.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 5: Cross-Context via Events | ✅ Enforced. Ledger only communicates via EventBus. |
| Rule 1: Dependency Inward | ✅ EventBus and handlers depend on abstractions. |
| Rule 6: Infrastructure as Plugin | ✅ `InMemoryEventBus` and `SmtpAdapter` are infrastructure details. |

---

## Backend Architecture — Cross-Context Integration

### DI Container
**File**: `app/di_container.py`

```
DIContainer
├── event_bus: InMemoryEventBus (singleton)
└── Subscriptions:
    ├── TransactionCompletedEvent → ReceiptEmailHandler.handle_completed
    ├── TransactionFailedEvent    → ReceiptEmailHandler.handle_failed
    ├── TransactionRefundedEvent  → ReceiptEmailHandler.handle_refunded
    └── PaymentInitiatedEvent     → ReceiptEmailHandler.handle_initiated
```

**Notes**:
- The `event_bus` is registered as a singleton within the container.
- Subscriptions are wired at application startup.
- Currently, only `EventBus` is accessed from the container in Ledger's web controller (`current_app.di_container.event_bus`). Full handler registration is incomplete (see TD-9 in Ledger HTTP API module).

### Event Bus
**Implementation**: `InMemoryEventBus`

- **Type**: Synchronous, in-memory publish/subscribe.
- **Publishing Rule**: Events are published **after** Unit of Work commit to ensure database consistency precedes side effects.
- **Failure Handling**: If an event handler fails, the database transaction is already committed. There is **no outbox pattern or retry mechanism**. Failures in handlers (e.g., email sending) cause exceptions but do not roll back the Ledger transaction.

**Subscribed Handlers**:
- `ReceiptEmailHandler.handle_completed(TransactionCompletedEvent)`
- `ReceiptEmailHandler.handle_failed(TransactionFailedEvent)`
- `ReceiptEmailHandler.handle_refunded(TransactionRefundedEvent)`
- `ReceiptEmailHandler.handle_initiated(PaymentInitiatedEvent)` — Note: This event originates from the Checkout context, not Ledger.

**ReceiptEmailHandler**:
- Receives the event, extracts `user_email`, `amount`, `currency_code`, `merchant_id`.
- Delegates to `SmtpAdapter.send()` for actual email delivery.

---

## Domain Events Reference

All events are frozen dataclasses defined in `src/ledger/domain/events/`. They are prepared inside the Unit of Work by handlers but published after `uow.commit()`.

| Event | Fields | Emitted By |
|---|---|---|
| `TransactionCompletedEvent` | `transaction_id`, `user_email`, `amount: Decimal`, `currency_code`, `merchant_id` | `CompleteFundsHandler` (after UoW commit) |
| `TransactionFailedEvent` | Same fields | `FailAndRefundHandler` (when Pending → Failed) |
| `TransactionRefundedEvent` | Same fields | `FailAndRefundHandler` (when Success → Refunded) |

**Publishing Rule**: Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). This prevents "phantom events" from rolling back transactions.

---

## Edge Cases & Known Issues

### EC-3: Phantom Events on Rollback
**Scenario**: An exception occurs inside `CompleteFundsHandler` after `uow.commit()` but before event publishing.
**Current Behavior**: The transaction is committed, but the event is never published. Downstream systems (Notifications) never receive the receipt trigger.
**Impact**: Data inconsistency between Ledger and Notifications contexts.
**Status**: Partially mitigated by publishing after UoW, but no retry/outbox exists.

### EC-4: Transaction ID Zero in Events
**Scenario**: A newly created transaction emits an event (e.g., if `HoldFundsHandler` were modified to emit events, or during completion of a just‑created transaction).
**Current Behavior**: `SqliteTransactionRepository.add()` returns `lastrowid` but does not assign it to `transaction.id`. The aggregate retains `id=0`.
**Impact**: All downstream consumers receiving events for new transactions will see `transaction_id=0`, making correlation impossible.
**Status**: **BUG**. Root cause in Infrastructure layer (see TD-3 in Ledger Infrastructure module).

---

## Notes & Technical Debt

*(No specific TD items are listed in the original master document exclusively for this module beyond those already referenced. The following are cross-references to items detailed in other modules that directly affect eventing.)*

- **TD-3 (Transaction ID Assignment Bug)**: Causes `transaction_id=0` in events for new transactions. Fixed in Infrastructure module.
- **EC-3 Mitigation**: A future outbox pattern would ensure events are stored within the UoW and published asynchronously with retry, eliminating phantom event inconsistencies.