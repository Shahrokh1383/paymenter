# Module 5: Identity Infrastructure
## Paymenter Project | Version 1.0.0

---

## 1. Overview
This module covers the **database schema** owned by Identity, the **cross‑context foreign key violations**, and the **dependency injection (DI) wiring** situation. It provides the common infrastructure that the other modules rely on.

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
    FOREIGN KEY (settlement_account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER NOT NULL, 
    account_id INTEGER NOT NULL, 
    card_number TEXT NOT NULL UNIQUE, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

**Schema Notes:**
- `users` and `merchants` are owned by Identity.
- `user_cards` is owned by Identity but references `accounts(id)` (Ledger table). This is a **cross‑context foreign key violation**.
- `merchants.settlement_account_id` references `accounts(id)` (Ledger table). Same cross‑context FK violation.
- The `currencies` table is **not** in Identity schema. It is defined in `LEDGER_SCHEMA`.

---

## 3. Dependency Injection & Wiring

**Central DI Container** (`src/app/di_container.py`):
```python
class DIContainer:
    def __init__(self):
        self.event_bus = InMemoryEventBus()
        register_ledger(self)
        register_notifications(self)
        register_checkout(self)
        # register_identity(self)  # <-- MISSING
```
**Identity DI Module:** `src/app/di/identity_di.py` — **Does not exist.**

**Current Wiring:**
- Ledger, Notifications, and Checkout are registered via dedicated modules.
- Identity handlers are manually instantiated inside `dashboard_controller.py` with raw `SqliteUnitOfWork()` and repository constructors.

**Example of Manual Wiring (Controller):**
```python
uow = SqliteUnitOfWork()
handler = RegisterUserHandler(uow, SqliteUserRepository(uow), LedgerAccountProvisioningAdapter(uow))
handler.handle(RegisterUserCommand(name=request.form['name'], phone_email=request.form['phone_email']))
```

**⚠️ Architectural Inconsistency:** Identity is the only context bypassing the centralized composition root. This violates the uniform wiring pattern and makes the controller untestable without monkey‑patching.

---

## 4. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Cross-Context Foreign Keys** | Medium | `settlement_account_id` and `account_id` FK to Ledger tables break schema isolation. |
| **No Identity DI Registration** | Medium | Identity is manually wired; all other contexts use `DIContainer`. |
| **Database connection leak** | Low | `SqliteUnitOfWork` uses nesting-level reference counting; exception outside `with` block may leak. |

---

## 5. Notes & Refactoring Roadmap

### Immediate
- Create `src/app/di/identity_di.py` and register all Identity handlers/repositories.
- Refactor `dashboard_controller.py` to resolve Identity handlers via `current_app.di_container`.

### Medium Term
- Remove cross‑context foreign keys; use local surrogate keys or event‑sourced references.

### Long Term
- Implement proper connection lifecycle management.
