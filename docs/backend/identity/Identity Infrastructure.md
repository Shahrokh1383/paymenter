# Module 5: Identity Infrastructure
## Paymenter Project | Version 1.1.0 (SSOT Revised)

---

## 1. Overview
This module documents the **database schema** owned by Identity, the **cross‑context foreign key violations**, the **local read model** (`user_summaries`), and the current **dependency injection (DI) wiring** status.

---

## 2. Database Schema

**Path:** `src/common/infrastructure/database/schemas/identity/identity.py`

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone_email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    settlement_account_id INTEGER,
    FOREIGN KEY (settlement_account_id) REFERENCES accounts(id)   -- ⚠️ Cross‑context FK
);

CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    card_number TEXT NOT NULL UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)             -- ⚠️ Cross‑context FK
);

CREATE TABLE IF NOT EXISTS user_summaries (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone_email TEXT NOT NULL,
    account_id INTEGER,
    account_number TEXT,
    card_number TEXT,
    balance TEXT DEFAULT '0.00',
    currency_code TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Schema Notes:**
- **Owned by Identity:** `users`, `merchants`, `user_cards`, `user_summaries`.
- **Cross‑context foreign keys:**
  - `merchants.settlement_account_id` → `accounts(id)` (Ledger table).
  - `user_cards.account_id` → `accounts(id)` (Ledger table).
  - `user_summaries.account_id` is **not** a foreign key – it stores the Ledger account ID as a plain value, avoiding a formal FK violation while preserving the ability to join logically. This is a pragmatic compromise until an event‑sourced reference replaces it.
- The `currencies` table lives in the **Ledger** schema, not Identity.
- The `user_summaries` table is a **local read model** kept up‑to‑date by domain event handlers within the Identity context.

---

## 3. Dependency Injection & Wiring

### 3.1 Central DI Container (`src/app/di_container.py`)
```python
class DIContainer:
    def __init__(self):
        self.event_bus = InMemoryEventBus()
        register_identity(self)      # ✅ Added in v1.1.0
        register_ledger(self)
        register_notifications(self)
        register_checkout(self)
```

### 3.2 Identity DI Module (`src/app/di/identity_di.py`) – **Now exists**
This module registers **domain event subscribers** in the DI container:

- `UserRegisteredReadModelHandler` → listens to `UserRegisteredEvent`
- `AccountCreatedReadModelHandler` → listens to `AccountCreatedEvent`
- `CardAssignedReadModelHandler` → listens to `CardAssignedEvent`
- `OnAccountCreatedHandler` → listens to `AccountCreatedEvent` (card assignment)

Each handler receives a `SqliteUnitOfWork()` instance (created inline in the lambda) and publishes further events via the EventBus as needed.

### 3.3 Dashboard Controller Wiring (Mixed)
**Ledger handlers** are obtained from the DI container:
```python
handler = current_app.di_container.get_topup_account_handler(uow)
```

**Identity command/query handlers** are still **instantiated manually** inside `dashboard_controller.py`:
```python
uow = SqliteUnitOfWork()
handler = RegisterUserHandler(uow, SqliteUserRepository(uow), current_app.di_container.event_bus)
handler.handle(...)
```
This inconsistency means the Identity context’s **application services** are not yet fully DI‑managed, while its **event handlers** are.

---

## 4. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Cross‑Context Foreign Keys** | Medium | `settlement_account_id` and `account_id` in `user_cards` still reference Ledger tables, violating schema isolation. |
| **Partial DI Registration** | Medium | Identity domain event handlers are registered, but command/query handlers are still manually wired in the controller. |
| **`user_summaries` FK Gap** | Low | `account_id` in `user_summaries` is a plain value without a foreign key constraint, which is intentional to avoid cross‑context FKs but lacks referential integrity. |

---

## 5. Notes & Refactoring Roadmap

### Immediate
- Register Identity command/query handler factories in `DIContainer` (e.g., `get_register_user_handler`, `get_all_users_handler`) and refactor the controller to use them.
- Move the `user_summaries` table definition to a dedicated read‑model schema file (still under Identity) to separate write and read concerns.

### Medium Term
- Remove cross‑context foreign keys entirely; replace with event‑borne references (e.g., store `account_number` instead of raw `account_id` for cross‑context lookups, or use a local identifier).

### Long Term
- Ensure consistent connection lifecycle across all UoW instances.