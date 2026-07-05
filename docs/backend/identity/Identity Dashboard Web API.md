# Module 6: Dashboard Web API
## Paymenter Project | Version 1.0.1 (SSOT Revised)

---

## 1. Overview
This module documents the **HTTP interface** served by the dashboard controller. The controller currently hosts both **Identity** and **Ledger** routes under the `/dashboard` prefix. The blueprint is defined in `src/identity/infrastructure/web/dashboard_controller.py`.

---

## 2. Controller & Routing

**Controller:** `dashboard_controller.py`  
**Blueprint:** `dashboard_bp`, url_prefix `/dashboard`

**Wiring pattern:**
- **Ledger handlers** are obtained from `current_app.di_container` (DI‑registered factories):
  - `get_create_currency_handler`
  - `get_all_accounts_handler`
  - `get_update_account_currency_handler`
  - `get_topup_account_handler`
  - `get_all_escrow_accounts_handler`
- **Identity handlers** are instantiated **inline** using `SqliteUnitOfWork` and specific repositories; they are **not** registered in the DI container. The `event_bus` is obtained from `current_app.di_container.event_bus`.
- **Flush**: After certain POST operations (`add_user`, `create_account`, `topup_account`), the outbox event bus is **flushed synchronously** to ensure read models are up‑to‑date for the subsequent redirect.

---

## 3. API Contract

### 3.1 Currencies

**GET /dashboard/currencies**
- **Description:** List all currencies.
- **Response:** HTML (`currencies.html`), data: `currencies`
- **Query Handler:** `GetAllCurrenciesHandler` (Identity, inline)

**POST /dashboard/currencies/add**
- **Description:** Create a new currency (delegates to Ledger).
- **Form Data:** `name`, `code`
- **Command:** `CreateCurrencyCommand` (Ledger)
- **Handler:** `container.get_create_currency_handler`
- **Success:** Redirect to `/dashboard/currencies`.
- **Error:** Flash message.

**POST /dashboard/currencies/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle currency active status (uses Identity handler, not the Ledger’s toggle).
- **Path Params:** `id` (currency ID), `is_active` (ignored; status is toggled in DB).
- **Command:** `ToggleCurrencyCommand` (Identity)
- **Handler:** `ToggleCurrencyHandler` (inline)
- **Success:** Redirect to `/dashboard/currencies`.

### 3.2 Users

**GET /dashboard/users**
- **Description:** List all users or search by query.
- **Query Params:** `query` (optional search string).
- **Response:** HTML (`users.html`), data: `users_list` (list of `UserSummaryDTO`), `query`, `currencies`
- **Handler:** `GetAllUsersHandler` or `SearchUsersHandler` (inline)

**POST /dashboard/users/add**
- **Description:** Register a new user.
- **Form Data:** `name`, `phone_email`
- **Command:** `RegisterUserCommand`
- **Handler:** `RegisterUserHandler` (inline, but receives `event_bus` from DI container)
- **Flush:** `current_app.di_container.event_bus.flush()` called after successful registration.
- **Success:** Redirect to `/dashboard/users`.
- **Error:** Flash message (e.g., `UserAlreadyExistsError`).

### 3.3 Accounts (Ledger, hosted in the same controller)

**GET /dashboard/accounts**
- **Description:** List all user accounts.
- **Response:** HTML (`accounts.html`), data: `accounts`, `currencies`, `users`
- **Query Handler:** `GetAllAccountsQuery` (Ledger, via DI container)

**POST /dashboard/accounts/create**
- **Description:** Create a new account for a user.
- **Form Data:** `user_id`, `currency_code`
- **Command:** `CreateAccountCommand` (Ledger)
- **Handler:** `CreateAccountHandler` (inline, uses DI’s `event_bus`)
- **Flush:** `current_app.di_container.event_bus.flush()` called after creation.
- **Success:** Redirect to `/dashboard/accounts` with success flash.
- **Error:** Flash message (e.g., “User does not exist.”).

**POST /dashboard/accounts/update-currency**
- **Form Data:** `account_id`, `currency_code`
- **Command:** `UpdateAccountCurrencyCommand` (Ledger)
- **Handler:** `container.get_update_account_currency_handler`
- **Success:** Redirect to `/dashboard/accounts`.

**POST /dashboard/accounts/topup**
- **Form Data:** `account_id`, `amount`
- **Command:** `TopupAccountCommand` (Ledger)
- **Handler:** `container.get_topup_account_handler`
- **Flush:** `current_app.di_container.event_bus.flush()` called after top‑up.
- **Success:** Redirect to the referring page (`dashboard.accounts` or wherever).

**GET /dashboard/escrow**
- **Description:** List escrow accounts.
- **Response:** HTML (`escrow_accounts.html`), data: `accounts`
- **Query Handler:** `GetAllEscrowAccountsQuery` (Ledger, via DI container)

### 3.4 Merchants

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML (`merchants.html`), data: `merchants_list`
- **Handler:** `GetAllMerchantsHandler` (inline)

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant (creates synthetic user, settlement account).
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Handler:** `OnboardMerchantHandler` (inline)
- **Success:** Redirect to `/dashboard/merchants`.
- **Error:** Flash message.

**POST /dashboard/merchants/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle merchant active status.
- **Path Params:** `id` (merchant ID), `is_active` (ignored; status flipped in DB).
- **Command:** `ToggleMerchantCommand`
- **Handler:** `ToggleMerchantHandler` (inline)
- **Success:** Redirect to `/dashboard/merchants`.

---

## 4. Flows

All business logic flows are documented in their respective domain modules.  
The controller’s responsibility is limited to:
- Parsing HTTP requests,
- Instantiating handlers (from DI or inline),
- Calling `handle()`,
- Flushing the outbox for certain commands,
- Redirecting or rendering templates.

---

## 5. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Manual Wiring for Identity** | Medium | Identity handlers (register user, toggle merchant, etc.) are instantiated inline without DI container support. This leads to tight coupling and duplication. Ledger handlers already use the DI container. |
| **Cross‑Context Routes in One Controller** | Medium | Identity and Ledger routes coexist in a single blueprint. This violates the separation of bounded contexts at the delivery layer. |
| **Unused `is_active` in toggle routes** | Low | Toggle endpoints for currencies and merchants include `is_active` in the URL, but it is ignored; the actual state is toggled directly in the database. |
| **No abstract DI for Identity** | Low | The dashboard controller directly imports and constructs handlers, bypassing the DI container that exists for Ledger. |

---

## 6. Notes & Refactoring Roadmap

### Immediate
- Register Identity handler factories in `DIContainer` (e.g., `get_register_user_handler`, `get_toggle_merchant_handler`) and refactor the controller to use them.
- Separate the dashboard blueprint into `identity_bp` and `ledger_bp` to align bounded context boundaries at the HTTP layer.

### Medium Term
- Move all Ledger‑specific endpoints to a dedicated `LedgerDashboardController` with its own blueprint.
- Unify the flush strategy (possibly in a decorator) to reduce duplication.

### Long Term
- Consider replacing server‑rendered HTML with a proper REST API and a separate frontend.

---