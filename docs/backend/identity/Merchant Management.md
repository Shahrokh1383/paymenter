# Module 2: Merchant Management  
## Paymenter Project | Version 1.0.2 (SSOT Revised – All Issues Resolved)

---

## 1. Overview
This module governs **Merchants** – business entities that process payments through the platform. Each merchant receives a unique API key for authentication and possesses a settlement account for fund collection.

**Current status:** Fully compliant with Constitution.md. All anti‑patterns and bugs have been eliminated.

---

## 2. Business Rules & Domain Invariants

### 2.1 Merchant Aggregate
- A `Merchant` must have a unique `api_key` (generated cryptographically, never set by clients).
- A `Merchant` must have a `settlement_account_id` referencing a Ledger account at the time of onboarding. No synthetic user is created; `accounts.user_id` is set to `NULL`.
- A `Merchant` can be toggled between `active` and `inactive` states. This is a soft-toggle; no data is deleted.
- **The aggregate's `toggle()` method is the sole authority for state changes.** The `ToggleMerchantHandler` fetches the entity, invokes `toggle()`, and persists via `update()`.

### 2.2 API Key Value Object
- Immutable (`frozen=True` dataclass).
- Value generated using `generate_api_key()`: format `pay_{secrets.token_urlsafe(32)}`.
- **Strict validation inside `__post_init__`**: must start with `pay_`, followed by exactly 43 URL‑safe characters.
- Invalid keys are rejected at construction time, preventing silent storage.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `Merchant`** (`src/identity/domain/entities/merchant.py`)
```python
@dataclass
class Merchant:
    id: int
    name: str
    api_key: ApiKey
    is_active: bool
    settlement_account_id: int

    def toggle(self) -> None:
        self.is_active = not self.is_active
```
- **Responsibility:** Represents a business entity authorized to process payments.
- **`toggle()` is now the only way to change active state.** Handlers no longer bypass it.

**Value Object: `ApiKey`** (`src/identity/domain/value_objects/api_key.py`)
```python
@dataclass(frozen=True)
class ApiKey:
    value: str
    VALID_KEY_REGEX = re.compile(r'^pay_[A-Za-z0-9\-_]{43}$')

    def __post_init__(self):
        if not self.VALID_KEY_REGEX.match(self.value):
            raise ValueError("ApiKey must start with 'pay_' and contain exactly 43 URL-safe characters.")
```
- **Fully validated at creation.**

**Port: `MerchantRepository`** (`src/identity/domain/repositories.py`)
```python
class MerchantRepository(ABC):
    @abstractmethod
    def add(self, merchant: Merchant) -> int: ...
    @abstractmethod
    def update(self, merchant: Merchant) -> None: ...
    @abstractmethod
    def get_by_id(self, merchant_id: int) -> Optional[Merchant]: ...   # NEW
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: ...
    @abstractmethod
    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]: ...
```
- **`get_by_id`** added; no `toggle_status`. The concrete repository must implement the full interface.

### 3.2 Application Layer

**Commands:**
| Command | Payload | Purpose |
|---------|---------|---------|
| `OnboardMerchantCommand` | `name: str` | Create a merchant and a settlement account. |
| `ToggleMerchantCommand` | `merchant_id: int` | Toggle merchant active status. |

**Handler: `OnboardMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `MerchantRepository`, `AccountProvisioningPort`, `CurrencyRepository`, `EventBus`
- **Actual flow:**
  1. Retrieve active currencies; if none, raise `ValueError`.
  2. Select the first active currency deterministically (by id).
  3. Provision a settlement account via `account_port.create_default_account(user_id=None, currency_id)` – no synthetic user.
  4. Create a `Merchant` with `id=0`, generated `ApiKey`, `is_active=True`, and the settlement account ID.
  5. Persist merchant via `merchant_repo.add(merchant)`.
  6. Commit UOW.
  7. **Publish `MerchantOnboardedEvent`** (via injected `EventBus`).

**Handler: `ToggleMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `MerchantRepository`, `EventBus`
- **Actual flow:**
  1. Fetch `Merchant` using `merchant_repo.get_by_id(cmd.merchant_id)`. Raise `ValueError` if not found.
  2. Call `merchant.toggle()` (domain logic).
  3. Persist via `merchant_repo.update(merchant)`.
  4. Commit UOW.
  5. **Publish `MerchantActivatedEvent` or `MerchantDeactivatedEvent`** accordingly.

**Query Handler: `GetAllMerchantsHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[MerchantSummaryDTO]` – a frozen dataclass with fields: `id`, `name`, `api_key`, `is_active`, `settlement_balance`.
- The repository now queries a **local read model table** `merchant_summaries`, completely decoupled from the Ledger context. No cross‑context JOIN.

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteMerchantRepository`** (`src/identity/infrastructure/persistence/sqlite_merchant_repository.py`)
- **Implements:** `MerchantRepository`
- **`add(merchant)`:** Inserts into `merchants` table.
- **`update(merchant)`:** Updates `is_active` by merchant id.
- **`get_by_id(merchant_id)`:** Fetches a row and reconstructs `Merchant` entity. Returns `None` if not found.
- **`get_all_summaries()`:** Queries `merchant_summaries` table and returns `List[MerchantSummaryDTO]`.
- **`get_by_api_key(api_key)`:** Select by `api_key` value, reconstructs entity.
- **`toggle_status` removed** – no longer exists.

**Database Schema** – table `merchants` defined in `identity.py`:
- Columns: `id`, `name`, `api_key` (TEXT UNIQUE), `is_active` (BOOLEAN DEFAULT 1), `settlement_account_id` (INTEGER REFERENCES accounts(id)).
- **New read model table `merchant_summaries`** (schema in `merchant_summaries_schema.py`):
  ```sql
  CREATE TABLE IF NOT EXISTS merchant_summaries (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      api_key TEXT NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT 1,
      settlement_balance TEXT DEFAULT '0.00'
  );
  ```
  Populated by domain event handlers; updated on toggle events.

**Read Model Handlers:**
- `MerchantOnboardedReadModelHandler`: inserts into `merchant_summaries` when `MerchantOnboardedEvent` is published.
- `MerchantToggledReadModelHandler`: updates `is_active` on `MerchantActivatedEvent` / `MerchantDeactivatedEvent`.

**Web Template** (`templates/merchants.html`)
- Displays columns: ID, Name, API Key (with copy button), Settlement Bal, Active, Action (toggle button).
- Uses `{{ m.settlement_balance }}` from the DTO's string field.
- Toggle form action: `/dashboard/merchants/toggle/<id>` (no `is_active` parameter).

---

## 4. API Contract

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML render with `merchants` (list of `MerchantSummaryDTO` objects with attributes `id`, `name`, `api_key`, `is_active`, `settlement_balance`).
- **Query Handler:** `GetAllMerchantsHandler`

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant (creates settlement account directly).
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`. Flashes error on failure.
- **Side Effects:** Publishes `MerchantOnboardedEvent`.

**POST /dashboard/merchants/toggle/<int:id>**
- **Description:** Toggle merchant active status. The server always flips the current state; no `is_active` parameter is expected or used.
- **Command:** `ToggleMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`. Raises 500 if merchant not found.
- **Side Effects:** Publishes `MerchantActivatedEvent` or `MerchantDeactivatedEvent`.

---

## 5. Flows

### 5.1 Onboard Merchant
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- POST /dashboard/merchants/add
    |
    v
[OnboardMerchantHandler]
    |-- 1. CurrencyRepository.get_active() -> first currency (by id)
    |-- 2. AccountProvisioningPort.create_default_account(user_id=None, currency_id) -> settlement_acc_id
    |-- 3. Create Merchant(id=0, name, api_key, is_active=True, settlement_account_id)
    |-- 4. MerchantRepository.add(merchant)
    |-- 5. UnitOfWork.commit()
    |-- 6. EventBus.publish(MerchantOnboardedEvent)
```
**Domain event triggers read model update:**
`MerchantOnboardedEvent` → `MerchantOnboardedReadModelHandler` inserts row into `merchant_summaries`.

### 5.2 Toggle Merchant Status
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- POST /dashboard/merchants/toggle/<id>
    |
    v
[ToggleMerchantHandler]
    |-- 1. MerchantRepository.get_by_id(id) -> merchant (raises if None)
    |-- 2. merchant.toggle()
    |-- 3. MerchantRepository.update(merchant)
    |-- 4. UnitOfWork.commit()
    |-- 5. EventBus.publish(MerchantActivatedEvent or MerchantDeactivatedEvent)
```
**Domain event triggers read model update:**
`MerchantActivatedEvent` / `MerchantDeactivatedEvent` → `MerchantToggledReadModelHandler` updates `is_active` in `merchant_summaries`.

### 5.3 Query Merchants
```
[Dashboard Controller] -- GET /dashboard/merchants
    |
    v
[GetAllMerchantsHandler]
    |-- merchant_repo.get_all_summaries()  (from merchant_summaries table)
    |-- Returns: List[MerchantSummaryDTO]
```
**No cross-context queries.**

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **All previous issues resolved** | — | No known issues remain. The system is now fully compliant with DDD and Constitution. |

---

## 7. Notes & Refactoring Roadmap

### Completed
- ✅ **DIP violation fixed** – `get_by_id` added; `toggle_status` removed.
- ✅ **Anemic domain resolved** – `toggle()` used; logic not in SQL.
- ✅ **Synthetic user removed** – settlement account linked directly to merchant (`user_id=NULL`).
- ✅ **Domain events emitted** – `MerchantOnboardedEvent`, `MerchantActivatedEvent`, `MerchantDeactivatedEvent`.
- ✅ **Bounded context leakage eliminated** – `merchant_summaries` read model replaces cross‑context JOIN.
- ✅ **Type safety restored** – `MerchantSummaryDTO` replaces raw `dict`.
- ✅ **API fixed** – toggle route no longer accepts `is_active`.
- ✅ **ApiKey validation** implemented.