# Transaction Application (Commands) Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

## Overview

The **Transaction Application (Commands)** module orchestrates the write-side lifecycle of financial transactions. It defines the three core commands (`HoldFundsCommand`, `CompleteFundsCommand`, `FailAndRefundCommand`) and their corresponding handlers, which coordinate the `Transaction` aggregate, `DoubleEntryLedger` domain service, `Account` aggregates (including dynamically resolved System Escrow accounts), and domain event publishing.

### Core Responsibilities
- **Hold Funds**: Initiate a pending transfer between two accounts via a dynamically resolved System Escrow account to maintain ledger balance.
- **Complete Funds**: Finalize a pending transaction, moving funds from Escrow to the receiver.
- **Fail & Refund**: Cancel a pending transaction (refunding from Escrow) or reverse a completed one (using system chargebacks/reversals).
- **Event Publishing**: Emit strictly isolated Domain Events (without Identity leakage) after a successful UoW commit for cross-context communication.
- **Unit of Work Coordination**: All handlers manage transactional boundaries via `UnitOfWork` and handle in-memory aggregate deduplication to prevent self-inflicted optimistic locking conflicts.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command and handler is strictly isolated in its own file. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Amounts are `Decimal` in commands, translated to `Money` (with `CurrencyCode` VO) in handlers. |
| Rule 5: Cross-Context via Events | ✅ Enforced. Handlers publish events outside the UoW. Identity data is excluded from Ledger events. |
| Rule 6: Infrastructure as Plugin | ✅ Handlers depend on abstractions (`SystemAccountResolverPort`, Repository ports, UoW, EventBus). |

---

## Business Rules

### BR-2: Currency Homogeneity
All operations involving two accounts require identical currencies. `CurrencyMismatchError` is raised if `from_acc.balance.currency != to_acc.balance.currency`. Enforced in `HoldFundsHandler` before calling the domain service. The comparison is strictly done using the normalized `CurrencyCode` Value Object.

### BR-4: Double-Entry Accounting
Every fund movement must balance. Handlers delegate to the `DoubleEntryLedger` domain service, which enforces the double-entry logic by routing pending funds through a dynamically resolved System Escrow account based on the transaction's currency.

### BR-7: Audit Trail
All state changes (Transaction status changes) must emit a `DomainEvent` for downstream audit and notification. Handlers prepare events inside the UoW but publish them strictly **after** `uow.commit()`.

---

## Backend Architecture — Application Layer

### Commands (Immutable Dataclasses)

| Command | Fields | Purpose |
|---|---|---|
| `HoldFundsCommand` | `from_account_id: int`, `to_account_id: int`, `amount: Decimal`, `merchant_id: Optional[int]`, `user_email: Optional[str]` | Initiate a pending transfer |
| `CompleteFundsCommand` | `transaction_id: int` | Finalize a pending transaction |
| `FailAndRefundCommand` | `transaction_id: int` | Fail/refund a transaction |

### Handlers

**HoldFundsHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`, `TransactionRepository`, `SystemAccountResolverPort`
- Flow:
  1. Load `from_acc` and `to_acc` by ID.
  2. Validate currency match between sender and receiver (using `CurrencyCode` VO).
  3. Convert primitive `Decimal` to `Money` VO using `from_acc.balance.currency`.
  4. Dynamically resolve `escrow_acc` via `SystemAccountResolverPort.get_escrow_account(currency)`.
  5. **In-Memory Deduplication**: If `from_acc` or `to_acc` is the same entity as `escrow_acc`, reassign references to prevent double-updates and optimistic locking crashes.
  6. Call `DoubleEntryLedger.hold_funds(...)` → returns `Transaction`.
  7. Update aggregates in repository.
  8. Add `Transaction` to repository (assigns `lastrowid` to aggregate).
  9. Commit UoW and return `txn_id`.

**CompleteFundsHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`, `TransactionRepository`, `EventBus`, `SystemAccountResolverPort`
- Flow:
  1. Load `Transaction` by ID.
  2. Load `to_acc` by ID.
  3. Dynamically resolve `escrow_acc` based on `txn.amount.currency`.
  4. **In-Memory Deduplication**: Align references if `to_acc` and `escrow_acc` are the same.
  5. Call `DoubleEntryLedger.complete_funds(txn, to_acc, escrow_acc)`.
  6. Update `txn`, `to_acc`, and `escrow_acc` in repositories.
  7. Commit UoW.
  8. Prepare `TransactionCompletedEvent` (uses correctly assigned `txn.id` and `payer_account_id`).
  9. Publish event outside UoW.

**FailAndRefundHandler**
- Dependencies: Same as CompleteFundsHandler.
- Flow:
  1. Load `Transaction`, `from_acc`, and `to_acc`.
  2. Dynamically resolve `escrow_acc`.
  3. **In-Memory Deduplication**: Align references to prevent self-inflicted `ConcurrencyException`.
  4. Call `DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc, escrow_acc)`.
  5. Update repositories conditionally based on the final status (`Failed` updates Escrow, `Refunded` does not).
  6. Commit UoW.
  7. Publish `TransactionFailedEvent` or `TransactionRefundedEvent` outside UoW.

---

## Backend Architecture — Domain Layer (Events)

### Domain Events
All frozen dataclasses defined in `src/ledger/domain/events/`. To strictly enforce bounded context boundaries (Constitution Rule 1 & 5), **Identity concepts (like `user_email`) are completely excluded from Ledger events.**

- `TransactionCompletedEvent`: `(transaction_id: int, payer_account_id: int, amount: Money, merchant_id: Optional[int])`
- `TransactionFailedEvent`: Same fields.
- `TransactionRefundedEvent`: Same fields.

*Note: The Notifications context uses an Anti-Corruption Layer (ACL) to resolve the `payer_account_id` back to a `user_email` for receipt routing.*

### Event Publishing Rule
Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). The `OutboxEventBusDecorator` intercepts the publish call, atomically persists the event to the `outbox_messages` table, and triggers the background relay worker, ensuring Approximate ACID compliance.

---

## Flows

### 1. Hold Funds
```text
[User/Checkout] → HoldFundsCommand(...)
  → HoldFundsHandler
    → UoW.begin()
    → AccountRepository.get_by_id(from_id)
    → AccountRepository.get_by_id(to_id)
    → Currency Match Validation (via CurrencyCode VO)
    → Money(command.amount, from_acc.balance.currency)
    → SystemAccountResolverPort.get_escrow_account(currency)
    → [In-Memory Deduplication of Aggregate References]
    → DoubleEntryLedger.hold_funds(from_acc, to_acc, amount, escrow_acc, ...)
      → from_acc.withdraw(amount)              [Debit Sender]
      → escrow_acc.deposit(amount)             [Credit Escrow]
      → Transaction.create_pending(...)        [Create Pending Record]
    → AccountRepository.update(from_acc)
    → AccountRepository.update(to_acc)         [If distinct]
    → AccountRepository.update(escrow_acc)     [If distinct]
    → TransactionRepository.add(txn)           → assigns lastrowid to txn.id
    → UoW.commit()
    → Return txn_id
```

### 2. Complete Funds
```text
[Merchant/SPA] → CompleteFundsCommand(transaction_id)
  → CompleteFundsHandler
    → UoW.begin()
    → TransactionRepository.get_by_id(id)
    → AccountRepository.get_by_id(txn.to_account_id)
    → SystemAccountResolverPort.get_escrow_account(txn.amount.currency)
    → [In-Memory Deduplication]
    → DoubleEntryLedger.complete_funds(txn, to_acc, escrow_acc)
      → txn.mark_as_success()                  [State Machine Check]
      → escrow_acc.withdraw(txn.amount)        [Debit Escrow]
      → to_acc.deposit(txn.amount)             [Credit Receiver]
    → TransactionRepository.update(txn)
    → AccountRepository.update(to_acc)
    → AccountRepository.update(escrow_acc)     [If distinct]
    → UoW.commit()
    → Prepare TransactionCompletedEvent
  → EventBus.publish(event)                    [After UoW]
    → OutboxEventBusDecorator persists to DB
    → Background Worker dispatches to Notification Context
```

### 3. Fail & Refund
```text
[Merchant/SPA] → FailAndRefundCommand(transaction_id)
  → FailAndRefundHandler
    → UoW.begin()
    → Load Transaction, from_acc, to_acc
    → Resolve escrow_acc dynamically
    → [In-Memory Deduplication]
    → DoubleEntryLedger.fail_and_refund(...)
      → IF status == 'Pending':
        → txn.mark_as_failed()
        → escrow_acc.withdraw(amount)         [Debit Escrow]
        → from_acc.deposit(amount)            [Credit Sender]
      → ELIF status == 'Success':
        → txn.mark_as_refunded()
        → from_acc.deposit(amount)            [Credit Sender]
        → to_acc.apply_system_reversal(amount) [Force Debit Receiver - TD-8]
    → Update repositories (Escrow updated ONLY if status == 'Failed')
    → UoW.commit()
    → Prepare TransactionFailedEvent OR TransactionRefundedEvent
  → EventBus.publish(event)
```

---

## Edge Cases & Known Issues

### EC-3: Phantom Events on Rollback — ✅ RESOLVED
**Previous Scenario**: An exception occurs inside handlers after `uow.commit()` but before event publishing, or events are published but the DB transaction rolls back.
**Resolution**: The `OutboxEventBusDecorator` has been implemented. Events are now atomically persisted to the `outbox_messages` table within the publish call, and a background `OutboxRelayWorker` handles safe delivery. Data consistency is guaranteed.

### EC-4: Transaction ID Zero in Events — ✅ RESOLVED
**Previous Scenario**: A newly created transaction emits an event, but `SqliteTransactionRepository.add()` never assigned `lastrowid` back to the aggregate.
**Resolution**: The `add()` method now explicitly mutates the aggregate (`transaction.id = cursor.lastrowid`) before returning. Event correlation works perfectly.

### EC-8: Self-Inflicted Optimistic Locking Conflicts — ✅ RESOLVED
**Previous Scenario**: If the `to_acc` and `escrow_acc` happened to be the exact same database record (or if an account interacted with itself), calling `repo.update()` twice on the same in-memory object would cause the second update to fail the `WHERE version = ?` check, raising a `ConcurrencyException`.
**Resolution**: Handlers now perform **In-Memory Deduplication** (e.g., `if to_acc.id == escrow_acc.id: to_acc = escrow_acc`). This ensures the repository only processes the aggregate once per UoW cycle.

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-7: Double-Entry Violation via "Limbo" Funds & Hardcoded Configs*
**Previous Violation**: Funds vanished during the Pending state, and Escrow was resolved via a hardcoded `SYSTEM_ESCROW_ACCOUNT_ID` in a `ledger_config.py` file.
**Resolution**: 
1. Introduced dynamic Escrow resolution via `SystemAccountResolverPort`. The infrastructure adapter (`SqliteSystemAccountResolver`) queries the DB for the system account matching the specific `CurrencyCode`.
2. The global ledger remains perfectly balanced at every micro-step without relying on fragile hardcoded configurations.
3. `ledger_config.py` was permanently deleted to eliminate dead code.

*(Resolved) TD-8: Unrecoverable Refund State on Spent Funds*
**Previous Violation**: Reversing a completed transaction called `to_acc.withdraw(amount)`. If the receiver had spent the funds, `InsufficientFundsError` was raised, crashing the refund process.
**Resolution**: Added a dedicated domain method `Account.apply_system_reversal(amount)`. This method forces a debit (allowing negative balances) specifically for system-initiated chargebacks, bypassing the standard user-facing `withdraw()` invariant checks.

*(Resolved) TD-11: Identity Leakage in Ledger Domain Events*
**Previous Violation**: Constitution Rule 1 & Rule 5. Ledger domain events carried a `user_email` string, leaking an Identity concept into the Ledger bounded context.
**Resolution**: Removed `user_email` from all Ledger transaction events. Replaced it with `payer_account_id: int`. The Notifications context now uses an ACL to resolve the email dynamically.

***