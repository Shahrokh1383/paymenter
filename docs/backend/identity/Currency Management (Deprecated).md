# Module 3: Currency Management (Deprecated)
## Paymenter Project | Version 1.0.0

---

## 1. Overview
**Warning:** This module documents legacy code that **must not be used** for new features.  
The authoritative ownership of the `currencies` table resides in the **Ledger** bounded context. The Identity context's currency commands, repository, and entity are **technical debt** and are retained only for backward compatibility of the toggle route.

---

## 2. Business Rules & Domain Invariants

### 2.1 Currency (Reference Data – Ledger Owned)
- A `Currency` must have a unique `code` (e.g., `USD`, `EUR`).
- A `Currency` can be activated or deactivated.
- **Invariant:** At least one active currency must exist before a merchant can be onboarded (because merchant settlement accounts require a currency denomination).
- **Ownership Warning:** Identity must not create, toggle, or manage currencies. The `AddCurrencyCommand` and `ToggleCurrencyCommand` in Identity are deprecated.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `Currency`** (`src/identity/domain/entities/currency.py`)
```python
@dataclass
class Currency:
    id: int
    name: str
    code: str        # Raw primitive; should be CurrencyCode VO (Technical Debt)
    is_active: bool

    def toggle(self) -> None:
        self.is_active = not self.is_active
```
- **Responsibility:** Local read‑only representation of Ledger reference data.
- **Warning:** This entity is redundant. Identity should consume Ledger’s read model.

**Port: `CurrencyRepository`** (`src/identity/domain/repositories.py`)
```python
class CurrencyRepository(ABC):
    @abstractmethod
    def add(self, currency: Currency) -> int: ...
    @abstractmethod
    def update(self, currency: Currency) -> None: ...
    @abstractmethod
    def get_all(self) -> List[Currency]: ...
    @abstractmethod
    def get_active(self) -> List[Currency]: ...
    @abstractmethod
    def exists_by_code(self, code: str) -> bool: ...
```
- **⚠️ Gap:** `toggle_status(self, currency_id: int)` is missing from the abstract interface but is called by `ToggleCurrencyHandler`.

### 3.2 Application Layer

**Commands (DEPRECATED):**
| Command | Payload | Purpose |
|---------|---------|---------|
| `AddCurrencyCommand` | `name: str`, `code: str` | Creates currency in Identity. **Dead code; no route uses it.** |
| `ToggleCurrencyCommand` | `currency_id: int` | Toggles currency in Identity. **Still used by `/dashboard/currencies/toggle` route.** |

**Handler: `AddCurrencyHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `CurrencyRepository`
- **Flow:** Check uniqueness via `exists_by_code`, create `Currency(id=0, ...)`, persist and commit.
- **⚠️ Deprecated:** Use `CreateCurrencyCommand` from Ledger context instead.

**Handler: `ToggleCurrencyHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `CurrencyRepository`
- **Flow:** Toggle active status via `currency_repo.toggle_status()`.
- **⚠️ DIP Violation:** `toggle_status` not declared on `CurrencyRepository` interface.

**Query: `GetAllCurrenciesQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** *(empty)*
- **Purpose:** Retrieve all currencies.

**Query Handler: `GetAllCurrenciesHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[Currency]` (Identity entity, not Ledger VO).

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteCurrencyRepository`** (`src/identity/infrastructure/persistence/sqlite_currency_repository.py`)
- **Implements:** `CurrencyRepository`
- **`add(currency)`:** Inserts into `currencies` (Ledger table).
- **`update(currency)`:** Updates `is_active`.
- **`toggle_status(currency_id)`:** Raw SQL `UPDATE currencies SET is_active = NOT is_active WHERE id = ?`.
- **`get_all()`:** SELECT all from `currencies`.
- **`get_active()`:** SELECT where `is_active = 1`.
- **`exists_by_code(code)`:** SELECT 1 check.
- **⚠️ Violation:** Operates on Ledger‑owned table. `toggle_status` not on abstract port.

---

## 4. API Contract

**GET /dashboard/currencies**
- **Description:** Retrieve all currencies.
- **Response:** HTML render (`currencies.html`) with `currencies_list`.
- **Query Handler:** `GetAllCurrenciesHandler`

**POST /dashboard/currencies/add**
- **Description:** Create a new currency **(this route correctly delegates to Ledger's `CreateCurrencyCommand`; Identity's `AddCurrencyCommand` is orphaned)**.
- **Form Data:** `name`, `code`
- **Command:** `CreateCurrencyCommand` (Ledger)
- **Success:** Redirect to `/dashboard/currencies`.

**POST /dashboard/currencies/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle currency active status **(uses deprecated Identity handler)**.
- **Path Params:** `id` (currency ID), `is_active` (unused).
- **Command:** `ToggleCurrencyCommand` (Identity — **Deprecated**)
- **Success:** Redirect to `/dashboard/currencies`.

---

## 5. Flows

### 5.1 Toggle Currency (Identity Path — Deprecated)
```
[Dashboard Controller] -- POST /dashboard/currencies/toggle/<id>/<is_active>
    |
    v
[ToggleCurrencyHandler]
    |-- 1. CurrencyRepository.toggle_status(currency_id)
    |-- 2. UnitOfWork.commit()
```
**Status:** This is a boundary violation; currency toggling should be a Ledger command that emits `CurrencyDeactivatedEvent`.

### 5.2 Query Currencies
```
[Dashboard Controller] -- GET /dashboard/currencies
    |
    v
[GetAllCurrenciesHandler]
    |-- SQL: SELECT * FROM currencies
    |-- Returns: List[Currency] (Identity entity)
```
**⚠️ Issues:** Reads from Ledger table but returns Identity entity (redundant mapping).

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Identity Owns Currency Logic** | Critical | Commands and repository exist in Identity but operate on Ledger data. |
| **Missing Abstract `toggle_status`** | High | DIP violation; handler depends on concrete implementation. |
| **No Domain Events** | Medium | No event emitted on currency state change. |
| **Toggle non‑existing currency** | – | UPDATE on missing ID silently succeeds. |

---

## 7. Notes & Refactoring Roadmap

### Immediate
- Remove `AddCurrencyCommand` and its handler (dead code).
- Re‑implement `/dashboard/currencies/toggle` to call a Ledger handler.

### Medium Term
- Remove Identity’s `Currency` entity and `SqliteCurrencyRepository`.
- Subscribe to `CurrencyDeactivatedEvent` from Ledger for any read‑model updates.

### Long Term
- Ensure all currency‑related API endpoints in the dashboard controller delegate to Ledger exclusively.

---