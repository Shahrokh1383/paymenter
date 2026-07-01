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

The **Transaction Application (Commands)** module orchestrates the write-side lifecycle of financial transactions. It defines the three core commands (`HoldFundsCommand`, `CompleteFundsCommand`, `FailAndRefundCommand`) and their corresponding handlers, which coordinate the `Transaction` aggregate, `DoubleEntryLedger` domain service, `Account` aggregates (including System Escrow), and domain event publishing.

### Core Responsibilities
- **Hold Funds**: Initiate a pending transfer between two accounts via a System Escrow account to maintain ledger balance.
- **Complete Funds**: Finalize a pending transaction, moving funds from Escrow to the receiver.
- **Fail & Refund**: Cancel a pending transaction (refunding from Escrow) or reverse a completed one (using system reversals).
- **Event Publishing**: Emit `TransactionCompletedEvent`, `TransactionFailedEvent`, or `TransactionRefundedEvent` after successful commit for cross-context communication.
- **Unit of Work Coordination**: All handlers manage transactional boundaries via `UnitOfWork`.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command/handler/config is isolated (`ledger_config.py` added for Escrow). |
| Rule 5: Cross-Context via Events | ✅ Enforced. Handlers publish events after UoW commit. |
| Rule 6: Infrastructure as Plugin | ✅ Handlers depend on abstractions (Repository ports, UoW, EventBus). |

---

## Business Rules

### BR-2: Currency Homogeneity
All operations involving two accounts require identical currencies. `CurrencyMismatchError` is raised if `from_acc.balance.currency != to_acc.balance.currency`. Enforced in `HoldFundsHandler` before calling the domain service.

### BR-4: Double-Entry Accounting
Every fund movement must balance. Handlers delegate to `DoubleEntryLedger` domain service which enforces the double-entry logic by routing pending funds through a System Escrow account.

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
  1. Load `from_acc`, `to_acc`, and `escrow_acc` (via `SYSTEM_ESCROW_ACCOUNT_ID` from `ledger_config.py`) by ID.
  2. Validate currency match between sender and receiver.
  3. Convert primitive `Decimal` to `Money` VO using `from_acc.balance.currency`.
  4. Call `DoubleEntryLedger.hold_funds(...)` → returns `Transaction`.
  5. Update `from_acc` and `escrow_acc` in repository.
  6. Add `Transaction` to repository (returns assigned `txn_id`).
  7. Commit UoW.
  8. Return `txn_id`.

**CompleteFundsHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`, `TransactionRepository`, `EventBus`
- Flow:
  1. Load `Transaction` by ID.
  2. Load `to_acc` and `escrow_acc` by IDs.
  3. Call `DoubleEntryLedger.complete_funds(txn, to_acc, escrow_acc)`.
  4. Update `txn`, `to_acc`, and `escrow_acc` in repositories.
  5. Commit UoW.
  6. Prepare `TransactionCompletedEvent` (uses correctly assigned `txn.id`).
  7. Publish event outside UoW.

**FailAndRefundHandler**
- Dependencies: Same as CompleteFundsHandler.
- Flow:
  1. Load `Transaction`, `from_acc`, `to_acc`, and `escrow_acc`.
  2. Call `DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc, escrow_acc)`.
  3. Update `txn`, `from_acc`, and `to_acc` in repositories.
  4. If status is `Failed`, also update `escrow_acc` in repository. (If `Refunded`, Escrow is untouched as it was zeroed out during completion).
  5. Commit UoW.
  6. Publish `TransactionFailedEvent` or `TransactionRefundedEvent` based on final status.

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
    → AccountRepository.get_by_id(SYSTEM_ESCROW_ACCOUNT_ID)
    → Currency Match Validation
    → Money(command.amount, from_acc.currency)
    → DoubleEntryLedger.hold_funds(from_acc, to_acc, amount, escrow_acc, ...)
      → from_acc.withdraw(amount)              [Debit Sender]
      → escrow_acc.deposit(amount)             [Credit Escrow - Fixes TD-7]
      → Transaction.create_pending(...)        [Create Pending Record]
    → AccountRepository.update(from_acc)
    → AccountRepository.update(escrow_acc)
    → TransactionRepository.add(txn)           → returns & assigns lastrowid
    → UoW.commit()
    → Return txn_id
```

### 2. Complete Funds
```
[User/Merchant] → CompleteFundsCommand(transaction_id)
  → CompleteFundsHandler
    → UoW.begin()
    → TransactionRepository.get_by_id(id)
    → AccountRepository.get_by_id(txn.to_account_id)
    → AccountRepository.get_by_id(SYSTEM_ESCROW_ACCOUNT_ID)
    → DoubleEntryLedger.complete_funds(txn, to_acc, escrow_acc)
      → txn.mark_as_success()                  [State Machine Check]
      → escrow_acc.withdraw(txn.amount)        [Debit Escrow - Fixes TD-7]
      → to_acc.deposit(txn.amount)             [Credit Receiver]
    → TransactionRepository.update(txn)
    → AccountRepository.update(to_acc)
    → AccountRepository.update(escrow_acc)
    → UoW.commit()
    → Prepare TransactionCompletedEvent
  → EventBus.publish(event)                    [After UoW]
    → OutboxEventBusDecorator persists to DB   [Fixes EC-3]
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
    → AccountRepository.get_by_id(SYSTEM_ESCROW_ACCOUNT_ID)
    → DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc, escrow_acc)
      → IF status == 'Pending':
        → txn.mark_as_failed()
        → escrow_acc.withdraw(amount)         [Debit Escrow]
        → from_acc.deposit(amount)            [Credit Sender]
      → ELIF status == 'Success':
        → txn.mark_as_refunded()
        → from_acc.deposit(amount)            [Credit Sender]
        → to_acc.apply_system_reversal(amount) [Force Debit Receiver - Fixes TD-8]
    → Update txn, from_acc, to_acc repositories
    → IF status == 'Failed': Update escrow_acc repository
    → UoW.commit()
    → Prepare TransactionFailedEvent OR TransactionRefundedEvent
  → EventBus.publish(event)
```

---

## Edge Cases & Known Issues

### EC-3: Phantom Events on Rollback — ✅ RESOLVED
**Previous Scenario**: An exception occurs inside `CompleteFundsHandler` after `uow.commit()` but before event publishing.
**Resolution**: The `OutboxEventBusDecorator` has been implemented and wired via `ledger_di.py`. Events are now atomically persisted to the `outbox_messages` table within the publish call, and a background `OutboxRelayWorker` handles safe delivery. Data consistency is guaranteed.

### EC-4: Transaction ID Zero in Events — ✅ RESOLVED
**Previous Scenario**: A newly created transaction emits an event, but `SqliteTransactionRepository.add()` never assigned `lastrowid` back to the aggregate.
**Resolution**: The `add()` method in `sqlite_transaction_repository.py` now explicitly mutates the aggregate (`transaction.id = cursor.lastrowid`) before returning. Event correlation works perfectly.

---

## Notes & Technical Debt

### TD-3: Transaction ID Assignment Bug — ✅ RESOLVED
**Previous Violation**: DDD Aggregate Identity Integrity
**Current Implementation**:
```python
# src/ledger/infrastructure/persistence/sqlite_transaction_repository.py
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    transaction.id = cursor.lastrowid  # Identity correctly synchronized
    return transaction.id
```

### TD-7: Double-Entry Violation via "Limbo" Funds — ✅ RESOLVED
**Previous Violation**: Strict double-entry accounting dictated that every debit must have an immediate credit. Funds were vanishing during the Pending state.
**Resolution**: Introduced a System Escrow Account (configured in `src/ledger/application/ledger_config.py` as `SYSTEM_ESCROW_ACCOUNT_ID`). 
- **Hold Flow:** Debit Sender → Credit Escrow.
- **Complete Flow:** Debit Escrow → Credit Receiver.
- **Fail Flow:** Debit Escrow → Credit Sender.
The global ledger now remains perfectly balanced at every micro-step. *(Note: DB must be seeded with the Escrow account ID prior to operation).*

### TD-8: Unrecoverable Refund State on Spent Funds — ✅ RESOLVED
**Previous Violation**: Reversing a completed transaction called `to_acc.withdraw(amount)`. If the receiver had spent the funds, `InsufficientFundsError` was raised, crashing the refund process.
**Resolution**: Added a dedicated domain method `Account.apply_system_reversal(amount)` in `account.py`. This method forces a debit (allowing negative balances) specifically for system-initiated chargebacks, bypassing the standard user-facing `withdraw()` invariant checks.