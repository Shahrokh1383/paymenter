# Module 1: User Management
## Paymenter Project | Version 1.1.1 (SSOT Refined)

## 1. Overview
This module manages **Users** – natural persons or system actors who hold financial accounts in the Paymenter platform.  
It covers user registration, querying, and the invariants that protect the User aggregate.

**Boundary note:** The User aggregate is owned entirely by the Identity context. Cross‑context concerns (like account creation) are now fully event‑driven and handled in *Module 4: Account Provisioning & Cross‑Context Integration*.

---

## 2. Business Rules & Domain Invariants

### 2.1 User Aggregate
- A `User` must have a unique `phone_email`, modelled as a `PhoneEmail` Value Object (VO). The VO enforces format validation (E.164 for phone numbers, RFC 5322 for email) and normalises the value (lowercase email, stripped whitespace).
- A `User` is created with `id=None` as a transient identifier; the infrastructure assigns the permanent `id` upon persistence.
- **No default account is provisioned automatically.** Account creation for a user is a separate, explicit operation performed later from the dashboard.
- A `User` may hold zero or more accounts (one-to-many via Ledger).
- A `User` may have zero or more cards mapped via `user_cards`.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `User`** (`src/identity/domain/entities/user.py`)
```python
@dataclass
class User:
    id: Optional[int]          # None until persisted
    name: str
    phone_email: PhoneEmail
```
- **Responsibility:** Represents a system actor.
- **Invariant:** `phone_email` uniqueness is enforced at the domain level through `UserRepository.exists_by_phone_email()` before persistence, and additionally protected by a database `UNIQUE` constraint.

**Value Object: `PhoneEmail`** (`src/identity/domain/value_objects/phone_email.py`)
- Encapsulates validation logic; raises `ValueError` for invalid formats.
- Normalises emails to lowercase and trims whitespace.

**Domain Event: `UserRegisteredEvent`** (`src/identity/domain/events/user_events.py`)
- Emitted after a new user is successfully persisted.
- Carries `user_id`, `name`, `phone_email` (as `PhoneEmail` VO).

**Port: `UserRepository`** (`src/identity/domain/repositories.py`)
```python
class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> int: ...
    @abstractmethod
    def get_all_summaries(self) -> List[UserSummaryDTO]: ...
    @abstractmethod
    def search_summaries(self, query: str) -> List[UserSummaryDTO]: ...
    @abstractmethod
    def exists_by_phone_email(self, phone_email: str) -> bool: ...
```

### 3.2 Application Layer

**Command: `RegisterUserCommand`** (`src/identity/application/commands/register_user_command.py`)
- **Payload:** `name: str`, `phone_email: str`
- **Purpose:** Register a new user (no account provisioning).

**Query: `GetAllUsersQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** *(empty)*
- **Purpose:** Retrieve all user summaries from the local read model.

**Query: `SearchUsersQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** `query: str`
- **Purpose:** Search users by name, account number, or card number on the local read model.

**Command Handler: `RegisterUserHandler`** (`src/identity/application/handlers/register_user_handler.py`)
- **Dependencies:** `UnitOfWork`, `UserRepository`, `EventBus`
- **Flow:**
  1. Validate `phone_email` by constructing `PhoneEmail` VO.
  2. Check uniqueness via `user_repo.exists_by_phone_email()` – raise `UserAlreadyExistsError` if duplicate.
  3. Create transient `User(id=None, name, phone_email_vo)`.
  4. Persist via `user_repo.add(user)` → receive `user_id`.
  5. Commit UOW.
  6. Publish `UserRegisteredEvent` to the EventBus.
- **No direct call to any Ledger adapter.** All cross‑context communication is event‑driven.

**Query Handler: `GetAllUsersHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[UserSummaryDTO]` from the `user_summaries` read model.
- **Data source:** Pure Identity‑owned table; no cross‑context JOINs.
- **Columns selected:** `user_id`, `name`, `phone_email`, `account_number`, `card_number`, `currency_code`.
  - **Note:** The `user_summaries` table still contains `account_id` and `balance` columns, but they are intentionally **not queried** by this module to keep the user list focused on identity information.

**Query Handler: `SearchUsersHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[UserSummaryDTO]` filtered by `LIKE` on `name`, `account_number`, `card_number` columns of `user_summaries`.

**DTO: `UserSummaryDTO`** (`src/identity/application/dto/user_summary.py`)
- Flat read‑model object with fields:
  - `user_id: int`
  - `name: str`
  - `phone_email: str`
  - `account_number: Optional[str]`
  - `card_number: Optional[str]`
  - `currency_code: Optional[str]`
- **Removed fields since v1.1.0:** `account_id`, `balance` – these were used only for the now‑removed top‑up actions on the user list page.

**Read Model Handlers** (`src/identity/application/handlers/read_model_handlers.py`)
- `UserRegisteredReadModelHandler` – inserts a new row into `user_summaries` on `UserRegisteredEvent`.
- `AccountCreatedReadModelHandler` – updates the row with `account_id`, `account_number`, `currency_code` on `AccountCreatedEvent` (from Ledger).
- `CardAssignedReadModelHandler` – updates the row with `card_number` on `CardAssignedEvent`.

**Cross‑Context Event Handlers**
- `OnAccountCreatedHandler` (Identity) – listens to `AccountCreatedEvent` (from Ledger) and assigns a new card to the user, inserting into `user_cards` and emitting `CardAssignedEvent`.

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteUserRepository`** (`src/identity/infrastructure/persistence/sqlite_user_repository.py`)
- **Implements:** `UserRepository`
- **`add(user)`:** Inserts into `users`; catches `IntegrityError` and translates to `UserAlreadyExistsError`. Returns `lastrowid`.
- **`exists_by_phone_email(phone_email)`:** Simple `SELECT` on `users`.
- **`get_all_summaries()`:** Queries `user_summaries` for `user_id, name, phone_email, account_number, card_number, currency_code` – **no balance or account_id**.
- **`search_summaries(query)`:** Same columns, with `LIKE` on name, account_number, card_number.
- All methods return strongly typed `UserSummaryDTO` objects.

**Database Schema** (`src/common/infrastructure/database/schemas/identity/identity.py`)
- `user_summaries` – read model owned by Identity context, synchronously updated via Domain Events.
  - Columns: `user_id INTEGER PRIMARY KEY`, `name TEXT`, `phone_email TEXT`, `account_id INTEGER`, `account_number TEXT`, `card_number TEXT`, `balance TEXT DEFAULT '0.00'`, `currency_code TEXT`.
  - The `account_id` and `balance` columns are **not used by the user list module** but are retained for potential future use by other read models or reporting.

---

## 4. API Contract

All routes are served by the Identity Dashboard Web UI (server‑rendered MVC).

**GET /dashboard/users**
- **Description:** List all users or search by query.
- **Query Params:** `query` (optional search string).
- **Response:** HTML render (`users.html`) with `users_list` (list of `UserSummaryDTO`), `query`, `currencies`.
- **Displayed columns:** ID, Name, Phone/Email, Account Num, Card Num, Currency.
- **No balance or top‑up actions are shown.**

**POST /dashboard/users/add**
- **Description:** Register a new user. No account is created.
- **Form Data:** `name`, `phone_email`
- **Command:** `RegisterUserCommand`
- **Success:** Redirect to `/dashboard/users` with success flash.
- **Error:** `UserAlreadyExistsError` → flash message; other errors → generic flash.

---

## 5. Flows

### 5.1 Register User
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- POST /dashboard/users/add
    |
    v
[RegisterUserHandler]
    |-- 1. Validate phone_email (PhoneEmail VO)
    |-- 2. Check uniqueness (user_repo.exists_by_phone_email)
    |-- 3. Create User(id=None, name, phone_email)
    |-- 4. UserRepository.add(user) -> user_id
    |-- 5. UnitOfWork.commit()
    |-- 6. EventBus.publish(UserRegisteredEvent)
    |
    v
[OutboxEventBusDecorator]
    |-- flush() called immediately after handler (ensures read model is up‑to‑date)
    v
[In-Memory EventBus]
    |-- UserRegisteredReadModelHandler inserts row into user_summaries
    |-- (Ledger context does NOT create account automatically)
```

### 5.2 Query Users
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- GET /dashboard/users?query=...
    |
    v
[GetAllUsersHandler] OR [SearchUsersHandler]
    |-- SELECT user_id, name, phone_email, account_number, card_number, currency_code FROM user_summaries
    |-- No JOINs, no balance/account_id
    |-- Returns List[UserSummaryDTO]
```

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Search uses LIKE on account/card** | Low | Works correctly, but may be slow on huge datasets without full‑text indexing. Acceptable for current scale. |

All previously documented issues (Critical/High) have been **fully resolved** in v1.1.0.  
The balance display and top‑up actions were intentionally **removed from the user list in v1.1.1** to maintain separation of concerns; they are handled exclusively on the Accounts page.

---

## 7. Notes & Refactoring Roadmap

### Completed (v1.1.0)
- ✅ Primitive Obsession eliminated – `PhoneEmail` VO with validation.
- ✅ Transient identity fixed – `id` is `None` until persisted.
- ✅ Domain uniqueness invariant enforced; `UserAlreadyExistsError` raised before DB insertion.
- ✅ Cross‑context coupling removed – user registration only emits `UserRegisteredEvent`.
- ✅ Hardcoded `currency_id=1` removed.
- ✅ Domain Events introduced (`UserRegisteredEvent`, `AccountCreatedEvent`, `CardAssignedEvent`).
- ✅ Cross‑context SQL JOINs eliminated – local `user_summaries` read model used.
- ✅ `IntegrityError` caught and translated to domain exception; friendly 400‑class errors in UI.
- ✅ Return types are now `List[UserSummaryDTO]` instead of raw DB rows.
- ✅ Controller uses `EventBus` from DI container.

### Completed (v1.1.1)
- ✅ **User list page simplified** – balance and top‑up actions removed; all account operations now performed on `/dashboard/accounts`.
- ✅ `UserSummaryDTO` cleaned to only expose identity‑related fields.
- ✅ `SqliteUserRepository` queries no longer fetch `balance` or `account_id`.
- ✅ **Account creation from Dashboard fully wired** – cross‑context event flow updates `user_summaries` and assigns cards correctly.
- ✅ Documentation updated to reflect the true state of the module.

---