# Transaction Application (Commands) Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture — Application Layer](#backend-architecture--application-layer)
   - [Commands](#commands)
   - [Handlers](#handlers)
4. [Backend Architecture — Domain Layer (Events)](#backend-architecture--domain-layer-events)
   - [Domain Events](#domain-events)
   - [Event Publishing Rule](#event-publishing-rule)
5. [Flows](#flows)
   - [Hold Funds](#1-hold-funds)
   - [Complete Funds](#2-complete-funds)
   - [Fail & Refund](#3-fail--refund)
6. [Edge Cases & Known Issues](#edge-cases--known-issues)
7. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Transaction Application (Commands)** module orchestrates the write-side lifecycle of financial transactions. It defines the three core commands (`HoldFundsCommand`, `CompleteFundsCommand`, `FailAndRefundCommand`) and their corresponding handlers, which coordinate the `Transaction` aggregate, `DoubleEntryLedger` domain service, `Account` aggregates, and domain event publishing.

### Core Responsibilities
- **Hold Funds**: Initiate a pending transfer between two accounts.
- **Complete Funds**: Finalize a pending transaction, moving funds to the receiver.
- **Fail & Refund**: Cancel a pending transaction or reverse a completed one.
- **Event Publishing**: Emit `TransactionCompletedEvent`, `TransactionFailedEvent`, or `TransactionRefundedEvent` after successful commit for cross-context communication.
- **Unit of Work Coordination**: All handlers manage transactional boundaries via `UnitOfWork`.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command/handler is isolated. |
| Rule 5: Cross-Context via Events | ✅ Enforced. Handlers publish events after UoW commit. |
| Rule 6: Infrastructure as Plugin | ✅ Handlers depend on abstractions (Repository ports, UoW, EventBus). |

---

## Business Rules

### BR-2: Currency Homogeneity
All operations involving two accounts require identical currencies. `CurrencyMismatchError` is raised if `from_acc.balance.currency != to_acc.balance.currency`. Enforced in `HoldFundsHandler` before calling the domain service.

### BR-4: Double-Entry Accounting
Every fund movement must balance. Handlers delegate to `DoubleEntryLedger` domain service which enforces the double-entry logic.

### BR-7: Audit Trail
All state changes (Transaction status changes) must emit a `DomainEvent` for downstream audit and notification. Handlers prepare events inside the UoW but publish them after `uow.commit()`.

---

## Backend Architecture — Application Layer

### Commands (Immutable Dataclasses)

| Command | Fields | Purpose |
|---|---|---|
| `HoldFundsCommand` | `from_account_id`, `to_account_id`, `amount: Decimal`, `merchant_id?`, `user_email?` | Initiate a pending transfer |
| `CompleteFundsCommand` | `transaction_id: int` | Finalize a pending transaction |
| `FailAndRefundCommand` | `transaction_id: int` | Fail/refund a transaction |

### Handlers

**HoldFundsHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`, `TransactionRepository`
- Flow:
  1. Load `from_acc` and `to_acc` by ID.
  2. Validate currency match between accounts.
  3. Convert primitive `Decimal` to `Money` VO using `from_acc.balance.currency`.
  4. Call `DoubleEntryLedger.hold_funds(...)` → returns `Transaction`.
  5. Update `from_acc` in repository.
  6. Add `Transaction` to repository (returns `lastrowid`).
  7. Commit UoW.
  8. Return `txn_id`.
- ⚠️ **Bug**: The returned `lastrowid` is never assigned to `transaction.id`. The aggregate remains with `id=0`.

**CompleteFundsHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`, `TransactionRepository`, `EventBus`
- Flow:
  1. Load `Transaction` by ID.
  2. Load `to_acc` by `txn.to_account_id`.
  3. Call `DoubleEntryLedger.complete_funds(txn, to_acc)`.
  4. Update `txn` and `to_acc` in repositories.
  5. Commit UoW.
  6. Prepare `TransactionCompletedEvent` (uses `txn.id` — **will be 0 if transaction was just created**).
  7. Publish event outside UoW.

**FailAndRefundHandler**
- Dependencies: Same as CompleteFundsHandler.
- Flow:
  1. Load `Transaction`, `from_acc`, `to_acc`.
  2. Call `DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc)`.
  3. Update all three aggregates.
  4. Commit UoW.
  5. Publish `TransactionFailedEvent` or `TransactionRefundedEvent` based on final status.

---

## Backend Architecture — Domain Layer (Events)

### Domain Events
All frozen dataclasses defined in `src/ledger/domain/events/`:
- `TransactionCompletedEvent`: `(transaction_id, user_email, amount: Decimal, currency_code, merchant_id)`
- `TransactionFailedEvent`: Same fields.
- `TransactionRefundedEvent`: Same fields.

### Event Publishing Rule
Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). This prevents "phantom events" from rolling back transactions.

---

## Flows

### 1. Hold Funds
```
[User/Checkout] → HoldFundsCommand(from_account_id, to_account_id, amount, merchant_id?, user_email?)
  → HoldFundsHandler
    → UoW.begin()
    → AccountRepository.get_by_id(from_id)
    → AccountRepository.get_by_id(to_id)
    → Currency Match Validation
    → Money(command.amount, from_acc.currency)
    → DoubleEntryLedger.hold_funds(from_acc, to_acc, amount, ...)
      → from_acc.withdraw(amount)              [Debit Sender]
      → Transaction.create_pending(...)        [Create Pending Record]
      → ⚠️ NO CREDIT TO to_acc (LIMBO — see TD-7 in Transaction Domain module)
    → AccountRepository.update(from_acc)
    → TransactionRepository.add(txn)           → returns lastrowid
    → UoW.commit()
    → Return txn_id (but txn.id still 0)
```

### 2. Complete Funds
```
[User/Merchant] → CompleteFundsCommand(transaction_id)
  → CompleteFundsHandler
    → UoW.begin()
    → TransactionRepository.get_by_id(id)
    → AccountRepository.get_by_id(txn.to_account_id)
    → DoubleEntryLedger.complete_funds(txn, to_acc)
      → txn.mark_as_success()                  [State Machine Check]
      → to_acc.deposit(txn.amount)             [Credit Receiver]
    → TransactionRepository.update(txn)
    → AccountRepository.update(to_acc)
    → UoW.commit()
    → Prepare TransactionCompletedEvent
  → EventBus.publish(event)                    [After UoW]
    → ReceiptEmailHandler.handle_completed()
      → SmtpAdapter.send()
```

### 3. Fail & Refund
```
[User/Merchant] → FailAndRefundCommand(transaction_id)
  → FailAndRefundHandler
    → UoW.begin()
    → TransactionRepository.get_by_id(id)
    → AccountRepository.get_by_id(txn.from_account_id)
    → AccountRepository.get_by_id(txn.to_account_id)
    → DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc)
      → IF status == 'Pending':
        → txn.mark_as_failed()
        → from_acc.deposit(amount)             [Refund Sender]
      → ELIF status == 'Success':
        → txn.mark_as_refunded()
        → from_acc.deposit(amount)             [Refund Sender]
        → to_acc.withdraw(amount)              [Debit Receiver]
        → ⚠️ May raise InsufficientFundsError if receiver spent funds (see TD-8)
    → Update all repositories
    → UoW.commit()
    → Prepare TransactionFailedEvent OR TransactionRefundedEvent
  → EventBus.publish(event)
```

---

## Edge Cases & Known Issues

### EC-3: Phantom Events on Rollback
**Scenario**: An exception occurs inside `CompleteFundsHandler` after `uow.commit()` but before event publishing.
**Current Behavior**: The transaction is committed, but the event is never published. Downstream systems (Notifications) never receive the receipt trigger.
**Impact**: Data inconsistency between Ledger and Notifications contexts.
**Status**: Partially mitigated by publishing after UoW, but no retry/outbox exists.

### EC-4: Transaction ID Zero in Events
**Scenario**: A newly created transaction emits an event (e.g., if HoldFunds were modified to emit events).
**Current Behavior**: `SqliteTransactionRepository.add()` returns `lastrowid` but does not assign it to `transaction.id`. The aggregate retains `id=0`.
**Impact**: All downstream consumers receiving events for new transactions will see `transaction_id=0`, making correlation impossible.
**Status**: **BUG**. See TD-3.

---

## Notes & Technical Debt

### TD-3: Transaction ID Assignment Bug
**Violation**: DDD Aggregate Identity Integrity
**Location**: `src/ledger/infrastructure/persistence/sqlite_transaction_repository.py` → `add()`
**Current**:
```python
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    return cursor.lastrowid  # Never assigned back
```
**Required Fix**:
```python
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    transaction.id = cursor.lastrowid  # Assign identity to aggregate
    return transaction.id
```
Without this fix, `TransactionCompletedEvent` and similar events carry `transaction_id=0` when the transaction was just created (relevant if HoldFunds ever emits events directly, or for any flow that queries the transaction ID after creation).