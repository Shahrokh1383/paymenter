
### 🏗️ Architectural Blueprint: Paymenter Webhook Engine

We are going to build a **"Store-and-Forward"** Webhook Delivery System. This ensures that if a merchant's server (Laravel) is down, Paymenter will not lose the event but will retry until it is delivered.

#### Phase 1: Merchant Configuration (The "Keys to the Castle")
**Goal:** We need a secure way for merchants to tell Paymenter *where* to send data and *how* to sign it.

**What we will build:**
1.  **Database Schema Update:**
    We will extend the `Merchants` table in your database to include:
    *   `webhook_url` (String): The endpoint URL (e.g., `https://merchant.com/api/webhooks/paymenter`).
    *   `webhook_secret` (String): A cryptographically secure random string (e.g., `whsec_8f7d...`).
    *   `webhook_enabled` (Boolean): A kill-switch to toggle webhooks on/off.

2.  **Admin Dashboard UI (Settings Page):**
    We will create a "Webhook Settings" view in the Paymenter Dashboard where the merchant (you) can generate a new Secret and set the URL.
    *   *Security Feature:* The Secret should only be shown **once** upon generation. After that, it is masked or hidden to prevent leakage.

---

#### Phase 2: Cryptographic Engine (The "Envelope Seal")
**Goal:** We must guarantee that the data sent to the merchant is authentic and hasn't been tampered with.

**What we will build:**
1.  **HMAC-SHA256 Signer Utility:**
    A dedicated utility class/function that takes the JSON payload and the Merchant's Secret, and generates a signature.
    *   **Logic:** `Signature = HMAC_SHA256(Raw_JSON_Body, Webhook_Secret)`
    *   **Header Format:** The result must be formatted specifically for the HTTP header: `X-Paymenter-Signature: sha256=<signature>`.

2.  **Timestamp Generator:**
    Every payload must include a `created_at` timestamp (ISO 8601). This allows the receiving merchant to reject "replay attacks" (old webhooks sent by hackers).

---

#### Phase 3: The Event Dispatcher (The "Courier")
**Goal:** This is the core engine that actually sends the HTTP requests. It must be robust and non-blocking.

**What we will build:**
1.  **The Dispatcher Service:**
    A background service that takes an Event Type (e.g., `payment.success`) and the Payload, and fires the HTTP POST request.
    *   **Non-Blocking:** This must run asynchronously (in a background thread or task queue) so that the Admin Dashboard doesn't freeze while waiting for the merchant's server to respond.

2.  **Retry Logic (Exponential Backoff):**
    If the merchant's server returns a `500 Error` or times out, Paymenter must not give up.
    *   *Attempt 1:* Immediate.
    *   *Attempt 2:* Wait 1 minute.
    *   *Attempt 3:* Wait 5 minutes.
    *   *Attempt 4:* Wait 30 minutes.
    *   *Final:* Mark as "Failed" in logs.

---

#### Phase 4: Audit & Observability (The "Black Box")
**Goal:** When things go wrong, you need to see exactly what happened without guessing.

**What we will build:**
1.  **`WebhookLogs` Table:**
    A dedicated database table to record every single attempt.
    *   `id`, `merchant_id`, `event_type`, `payload` (JSON), `status_code` (e.g., 200, 401, 500), `response_body`, `attempts_count`, `last_attempt_at`.

2.  **Dashboard "Webhook History" View:**
    A page in the Admin Dashboard where you can see a list of recent webhooks.
    *   *Green Check:* Delivered successfully.
    *   *Red X:* Failed (Click to view the error message from the merchant's server).
    *   *Retry Button:* Manually force Paymenter to resend a failed webhook.

---

#### Phase 5: Integration Triggers (The "Tripwires")
**Goal:** We need to hook into your existing Admin logic to fire these events.

**What we will modify:**
1.  **The "Complete" Action:**
    In the Admin Dashboard controller where you click **[Complete Transaction]**, we will inject a call to the Dispatcher:
    `Dispatcher.fire(merchant, 'payment.completed', transaction_data)`

2.  **The "Fail" Action:**
    In the **[Fail Transaction]** logic:
    `Dispatcher.fire(merchant, 'payment.failed', transaction_data)`

3.  **The "Refund" Action:**
    In the **[Refund]** logic:
    `Dispatcher.fire(merchant, 'payment.refunded', refund_data)`

---

### 📊 Summary of Deliverables for Paymenter

| Component | Description | Priority |
| :--- | :--- | :--- |
| **DB Migration** | Add `webhook_url` and `webhook_secret` to Merchant model. | High |
| **Crypto Utility** | Function to generate HMAC-SHA256 signatures. | High |
| **Dispatcher Logic** | HTTP Client to POST data with headers & retries. | High |
| **Audit Logging** | DB Table to store request/response history. | Medium |
| **Admin UI** | Settings page to configure URLs and view logs. | Medium |
