*Paymenter Project*

# Project Blueprint: Custom Payment Gateway Simulator

### 1. Project Philosophy and Purpose
This is a **local, simulated Payment Gateway** designed exclusively as a developer testing tool. Its purpose is to replace real banking APIs during the development of backend applications (like Laravel or Django). It allows developers to simulate the complete lifecycle of financial transactions—checking accounts, holding funds, processing payments, and handling failures with automatic refunds—without risking real money or dealing with complex bank integrations. 

### 2. Technology Stack
*   **Backend:** Flask (Python) - Lightweight and fast.
*   **Database:** SQLite (via Python's `sqlite3`) - Zero configuration, stored as a single local file.
*   **Frontend:** Plain HTML, CSS, and Vanilla JavaScript - Simple, without complex frameworks.
*   **Deployment:** A Windows `.bat` file to install dependencies, start the Flask server, and automatically open the dashboard in the browser.

### 3. Core Architectural Concept: Double-Entry Bookkeeping
The most critical rule of this system is: **Money never appears out of nowhere, and it never disappears. Every transaction must have a clear Source and Destination.** 
Therefore, every entity that sends or receives money (whether it's a user buying a product or the Laravel project selling it) must have a dedicated Bank Account in the system.

---

### 4. Database Structure
The system relies on 5 interconnected tables:

1.  **Currencies:** Defines the monetary units supported by the gateway.
    *   `id`, `name` (e.g., Toman, US Dollar), `code` (e.g., TOM, USD), `is_active`.
2.  **Merchants (Organizations):** Represents the external projects (Laravel/Django) that use the gateway API.
    *   `id`, `name`, `api_key` (unique, auto-generated), `is_active`, `settlement_account_id` (links to the Accounts table).
3.  **Users:** The individuals who own bank accounts.
    *   `id`, `name`, `phone/email`.
4.  **Accounts:** The actual wallets holding balances.
    *   `id`, `user_id` (can be a normal user OR the Merchant's owner), `currency_id`, `account_number` (unique), `card_number` (unique), `balance`.
5.  **Transactions:** The immutable log of all financial movements.
    *   `id`, `merchant_id` (if initiated via API), `from_account_id`, `to_account_id`, `amount`, `currency_id`, `status` (`pending`, `success`, `failed`, `refunded`), `created_at`.

---

### 5. Comprehensive Feature List

#### A. Currency Management (Dashboard)
*   Add new currencies dynamically (e.g., EUR, GBP).
*   Activate/Deactivate currencies. (Deactivated currencies prevent the creation of new accounts, but existing accounts remain functional).

#### B. Merchant (Organization) Management (Dashboard)
*   Create new Merchants (e.g., "My Laravel E-Commerce").
*   Automatically generate a unique `api_key` for each merchant with one click.
*   Automatically create a **Settlement Bank Account** for the merchant (selecting the desired currency). The merchant cannot receive API payments without this account.
*   Activate/Deactivate merchants (blocks API access instantly).
*   Copy the API key to paste into the Laravel `.env` file.

#### C. User & Account Management (Dashboard)
*   Create new Users.
*   **Multiple Accounts:** Create unlimited bank accounts per user. When creating an account, you select the specific Currency (e.g., Ali can have one Toman account, one USD account, and a second Toman account).
*   The system auto-generates unique 16-digit Card Numbers and standard Account Numbers.
*   **Search:** Find users instantly by Name, Account Number, or Card Number.
*   **Manual Top-Up:** Select any user account and manually add any amount of money (simulating a bank deposit or physical cash injection).

#### D. Transaction Simulator (Dashboard & API)
This is the heart of the system, operating on a strict **Hold -> Complete/Fail** mechanism.

*   **Manual Transfer (Dashboard):** 
    *   You input a Source Account, Destination Account, Amount, and Currency.
    *   System validates: Do both accounts exist? Do currencies match? Does the source have enough balance?
    *   If valid, money is **deducted** from the Source, and a `Pending` transaction is created.
*   **Admin Decision (Dashboard):**
    *   View all Pending transactions.
    *   Two buttons per transaction:
        *   **[Complete]:** Money is officially **added** to the Destination Account. Status becomes `Success`.
        *   **[Fail]:** The **Refund** mechanism triggers. Money is **returned** to the Source Account. Destination gets nothing. Status becomes `Failed/Refunded`.

#### E. API Endpoints (Backend Integration)
All endpoints require a valid `x-api-key` header. The system identifies the Merchant via this key.

*   **`POST /api/pay` (Initiate Payment):**
    *   Input: `destination_card_number`, `amount`, `currency_code`.
    *   Logic: 
        1. Authenticate Merchant.
        2. Verify Merchant has a valid, active Settlement Account matching the `currency_code`. **(If not, FAIL)**
        3. Verify `destination_card_number` exists and matches the currency. **(If not, FAIL)**
        4. Verify the User has enough balance. **(If not, FAIL)**
        5. If all pass: Deduct money from User, create `Pending` transaction (from User -> to Merchant), return `transaction_id` and `Pending` status to Laravel.
*   **`POST /api/refund` (Programmatic Refund):**
    *   Input: `transaction_id`.
    *   Logic: Returns the money to the source account and marks the transaction as `Refunded`.
*   **`GET /api/verify/<transaction_id>` (Check Status):**
    *   Logic: Allows Laravel to poll the gateway and check if the admin has clicked Complete or Fail, returning the current status.

#### F. Launcher (Windows Integration)
*   A `.bat` file that starts the Flask server and immediately opens `http://127.0.0.1:5000` in the default web browser, ready to use.

---

### 6. Real-World Workflow Example (Laravel Integration)

1.  **Setup:** You create a Merchant ("Laravel Shop") in the dashboard, which auto-creates a Toman Settlement Account for it. You copy the `api_key` to your Laravel `.env` file.
2.  **Fund User:** You create a User ("Ali"), create a Toman Account for him, and manually Top-Up his account with 1,000,000 Toman.
3.  **Purchase:** Ali buys a 200,000 Toman item on your Laravel site.
4.  **API Request:** Laravel sends a POST request to `/api/pay` with Ali's card number and the amount.
5.  **Gateway Validation:** Flask checks the API key, sees the Merchant has a Toman account, checks Ali's card exists, and checks Ali has enough balance (1,000,000 >= 200,000).
6.  **Hold:** Flask deducts 200,000 from Ali's account (Ali's balance is now 800,000). A `Pending` transaction is created.
7.  **Simulation:** You go to the Flask Dashboard. You see the 200,000 Toman pending transaction.
8.  **Completion:** You click **[Complete]**. The 200,000 Toman is added to the "Laravel Shop" Settlement Account. Laravel polls `/api/verify`, sees `Success`, and confirms Ali's order.

*(If you had clicked **[Fail]**, the 200,000 Toman would instantly be refunded back to Ali's account, restoring his balance to 1,000,000, and Laravel would receive the `Failed` status, canceling the order).*