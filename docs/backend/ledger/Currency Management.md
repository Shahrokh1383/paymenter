# Currency Management (Canonical & Refactored)
## Paymenter Project | Version 2.0.0 (SSOT - Current Architecture)

---

## 1. Overview
This module documents the **canonical, production-ready** architecture for Currency Management. 
The absolute ownership of the `currencies` table, business logic, and state transitions resides exclusively within the **Ledger** bounded context. The Identity context has been completely decoupled from currency writes and relies solely on Ledger's Read Models (via CQRS) for UI composition. All previous technical debt, boundary violations, and anemic domain models have been eradicated.

---

## 2. Business Rules & Domain Invariants

### 2.1 Currency (Core Aggregate – Ledger Owned)
- A `Currency` must have a unique `code` (e.g., `USD`, `EUR`), strictly enforced via the `CurrencyCode` Value Object.
- A `Currency` can be activated or deactivated. State transitions are encapsulated within the Aggregate Root.
- **Invariant:** At least one active currency must exist before a merchant can be onboarded (because merchant settlement accounts require a currency denomination).
- **System Bootstrap:** Creating a new currency automatically bootstraps a corresponding System Escrow Account (Account Number: `9000000000 + currency_id`) to support the double-entry ledger balancing mechanism.
- **Ownership Rule:** No other bounded context (including Identity) may create, update, or toggle currencies. All mutations must pass through Ledger's Application Commands.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `Currency`** (`src/ledger/domain/entities/currency.py`)
```python
@dataclass
class Currency:
    id: int
    name: str
    code: CurrencyCode  # Value Object (Rule 3: No Primitive Obsession)
    is_active: bool

    @classmethod
    def create(cls, id: int, name: str, code: CurrencyCode) -> 'Currency': ...

    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
    def toggle(self) -> None: ...
```
- **Responsibility:** Rich Aggregate Root protecting state invariants (Rule 4). It dictates how state transitions occur, preventing anemic domain logic.

**Domain Events** (`src/ledger/domain/events/currency_events.py`)
- `CurrencyCreatedEvent(currency_id, name, code)`
- `CurrencyActivatedEvent(currency_id, code)`
- `CurrencyDeactivatedEvent(currency_id, code)`

**Port: `CurrencyRepository`** (`src/ledger/domain/repositories.py`)
```python
class CurrencyRepository(ABC):
    @abstractmethod
    def get_by_id(self, currency_id: int) -> Optional[Currency]: pass
    
    @abstractmethod
    def get_by_code(self, code: CurrencyCode) -> Optional[Currency]: pass
    
    @abstractmethod
    def add(self, currency: Currency) -> int: pass
    
    @abstractmethod
    def update(self, currency: Currency) -> None: pass
```

### 3.2 Application Layer

**Commands:**
| Command | Payload | Purpose |
|---------|---------|---------|
| `CreateCurrencyCommand` | `name: str`, `code: str` | Creates currency & bootstraps escrow account. Emits `CurrencyCreatedEvent`. |
| `ToggleCurrencyCommand` | `currency_id: int` | Loads aggregate, toggles state, persists, and emits Activation/Deactivation events. |

**Queries & DTOs:**
- `GetAllCurrenciesQuery` / `GetActiveCurrenciesQuery` -> Returns `List[CurrencySummaryDTO]`.
- `CurrencyQueryPort` (`src/ledger/application/ports/currency_query_port.py`): Abstract interface for read-optimized UI composition.

**Handlers:**
- `CreateCurrencyHandler`: Enforces uniqueness (`CurrencyAlreadyExistsError`), creates Aggregate, bootstraps Escrow Account, and publishes events.
- `ToggleCurrencyHandler`: Enforces existence (`CurrencyNotFoundError`), mutates Aggregate state, and publishes events.
- `GetAllCurrenciesHandler` / `GetActiveCurrenciesHandler`: Delegates to `CurrencyQueryPort` for fast read-model retrieval.

### 3.3 Infrastructure Layer

**Persistence Adapters:**
1. **`SqliteCurrencyRepository`** (`src/ledger/infrastructure/persistence/sqlite_currency_repository.py`)
   - Implements Domain `CurrencyRepository`.
   - Maps SQLite rows to Domain Aggregates (using `CurrencyCode` VO).
   - Handles `UPDATE` and `INSERT` operations strictly for the Command side.

2. **`SqliteCurrencyQueryRepository`** (`src/ledger/infrastructure/persistence/sqlite_currency_query_repository.py`)
   - Implements `CurrencyQueryPort`.
   - Bypasses Aggregate hydration to return lightweight `CurrencySummaryDTO`s directly to the Delivery layer for UI rendering.

---

## 4. API Contract

**GET /dashboard/currencies**
- **Description:** Retrieve all currencies for the management dashboard.
- **Resolution:** `current_app.di_container.get_all_currencies_handler(uow).handle(GetAllCurrenciesQuery())`
- **Response:** HTML render (`currencies.html`).

**POST /dashboard/currencies/add**
- **Description:** Create a new currency.
- **Form Data:** `name`, `code`
- **Resolution:** `current_app.di_container.get_create_currency_handler(uow).handle(CreateCurrencyCommand(...))`

**POST /dashboard/currencies/toggle/<int:id>**
- **Description:** Toggle currency active status. 
- **Note:** The legacy `<int:is_active>` path parameter has been **permanently removed** to reflect the true intent of the endpoint (toggling based on current state).
- **Resolution:** `current_app.di_container.get_toggle_currency_handler(uow).handle(ToggleCurrencyCommand(id))`

---

## 5. Flows

### 5.1 Toggle Currency (Canonical Ledger Path)
```
[Dashboard Controller] -- POST /dashboard/currencies/toggle/<id>
    |
    v
[DI Container] -> Resolves [ToggleCurrencyHandler]
    |
    v
[ToggleCurrencyHandler]
    |-- 1. currency_repo.get_by_id(id) -> Raises CurrencyNotFoundError if missing
    |-- 2. currency.toggle() (Domain Logic)
    |-- 3. currency_repo.update(currency)
    |-- 4. uow.commit()
    |-- 5. event_bus.publish(CurrencyActivated/DeactivatedEvent)
```

### 5.2 UI Composition (Cross-Context Read)
```
[Dashboard Controller] -- GET /dashboard/users (or /accounts)
    |
    v
[Identity Queries] -> Fetches Users/Accounts
[Ledger Queries]   -> get_active_currencies_handler().handle(GetActiveCurrenciesQuery())
    |
    v
[Controller] -> Composes both datasets into the Jinja Template context.
```
*Identity remains completely ignorant of Currency domain logic, consuming only Ledger's Read Models.*

---

## 6. Resolved Legacy Issues & Edge Cases

| Previous Issue | Severity | Resolution Status |
|----------------|----------|-------------------|
| **Identity Writes to Ledger Table** | Critical | **RESOLVED:** Identity currency write paths entirely purged. Ledger is SSOT. |
| **Missing Abstract `toggle_status` (DIP)** | High | **RESOLVED:** Replaced raw SQL hack with rich Domain Aggregate methods and strict Ports. |
| **Toggle Endpoint API Bug** | Medium | **RESOLVED:** Removed unused `<int:is_active>` path parameter. |
| **Silent Failure on Non-existent Toggle** | Low | **RESOLVED:** Handler now explicitly throws `CurrencyNotFoundError`. |
| **Anaemic Domain Model** | High | **RESOLVED:** `Currency` is now a rich Aggregate encapsulating `toggle()`, `activate()`, `deactivate()`. |
| **Direct Infra Instantiation in Controller** | Critical | **RESOLVED:** Delivery layer now strictly relies on `DIContainer` (Rule 1 & 6). |

---

## 7. Architectural Notes & Maintenance

### Strict Dependency Inversion (Rule 1)
The `dashboard_controller.py` **must never** import or instantiate `SqliteUnitOfWork` or concrete repositories directly for handler resolution. All handlers must be fetched via `current_app.di_container.get_<handler_name>(uow)`.

### Cross-Context Communication (Rule 5)
If the Identity context requires local caching or read-model updates based on currency state changes in the future, it **must not** query the Ledger database directly. Instead, it must subscribe to `CurrencyActivatedEvent` and `CurrencyDeactivatedEvent` via the `EventBus` in `src/app/di/identity_di.py`.

### Dead Code Policy (Rule 2)
All legacy Identity currency files (`entities/currency.py`, `sqlite_currency_repository.py`) and commands/handlers have been permanently deleted. Any attempt to recreate currency logic outside the Ledger bounded context will result in immediate PR rejection.