# Paymenter Gateway: Laravel Integration Guide (Hosted Payment Page)

**Version 3.2**  

## 1. Prerequisites

1.  **Local SMTP Sink:** Start your `smtp-server` project on port `1025` to intercept OTPs and Receipts.
2.  **Paymenter Dashboard:** Start Paymenter (default `http://127.0.0.1:5000`) and ensure the background worker is running (`flask webhook-worker`).
3.  **Active Currency & Merchant:** Create a currency (e.g., `USD`) and a Merchant in the Paymenter Dashboard.
4.  **Configure Webhooks:** In the Paymenter Dashboard, under the Merchant, set your `webhook_url` (e.g., `https://your-app.com/api/webhooks/paymenter`), generate a `webhook_secret`, and enable it.
5.  **Copy API Key & Webhook Secret:** Save the Merchant's API Key and the Webhook Secret.
6.  **Test User:** Create a User in Paymenter and top up their balance so payments can be tested.

---

## 2. Laravel Configuration

**.env**
```env
PAYMENTER_API_URL=http://127.0.0.1:5001/api
PAYMENTER_API_KEY=your_api_key_here
PAYMENTER_CURRENCY=USD
PAYMENTER_WEBHOOK_SECRET=your_webhook_secret_here
```

**config/services.php**
```php
'paymenter' => [
    'url' => env('PAYMENTER_API_URL'),
    'key' => env('PAYMENTER_API_KEY'),
    'currency' => env('PAYMENTER_CURRENCY', 'USD'),
    'webhook_secret' => env('PAYMENTER_WEBHOOK_SECRET'),
],
```

---

## 3. Transaction ID Format (Critical)

Paymenter issues transaction IDs as **32-character lowercase hexadecimal strings**, *without dashes*.  
Example: `b2ae55eba7704feeac0b9e4c69b0285b`

- **Do not** use Laravel's `Str::isUuid()` or route `->whereUuid()` on this value; those expect 36-character UUIDs with dashes.
- **Always treat `transaction_id` as a plain string.**

### Route Constraint for Verification
When defining your verification endpoint, use a regex that matches exactly 32 hex characters:

```php
Route::get('verify/{transactionId}', [PaymentController::class, 'verify'])
    ->where('transactionId', '^[0-9a-f]{32}$');
```

This prevents Laravel from rejecting the request before your controller runs.

---

## 4. Domain Separation – Keep Payment Logic in Its Own Context

**Important Architectural Rule:**  
Payment verification is a **payment-domain** concern, not a subscription, order, or product concern.  
Do **not** place the `verify` endpoint inside a `SubscriptionController` or `OrderController`. Create a dedicated `PaymentController` (or similar) responsible for:

- Looking up a `Payment` record by `gateway_transaction_id`.
- Returning the payment status and a `deadline` for client-side polling.

This ensures that projects without subscriptions (e.g., one-time product purchases) can reuse the exact same pattern without confusion.

---

## 5. Paymenter Service Class

Create `app/Services/PaymenterService.php`.

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

class PaymenterService
{
    private string $apiUrl;
    private string $apiKey;

    public function __construct()
    {
        $this->apiUrl = config('services.paymenter.url');
        $this->apiKey = config('services.paymenter.key');
    }

    private function httpClient()
    {
        return Http::withHeaders(['x-api-key' => $this->apiKey])->timeout(15);
    }

    public function createSession(float $amount, string $currencyCode, string $userEmail, string $callbackUrl): array
    {
        $response = $this->httpClient()->post("{$this->apiUrl}/pay", [
            'amount'        => $amount,
            'currency_code' => $currencyCode,
            'user_email'    => $userEmail,
            'callback_url'  => $callbackUrl,
        ]);

        if ($response->successful()) {
            return $response->json(); // Contains 'token' and 'payment_url'
        }
        throw new \Exception($response->json('error', 'Session creation failed.'), $response->status());
    }

    public function verify(string $transactionId): array
    {
        $response = $this->httpClient()->get("{$this->apiUrl}/verify/{$transactionId}");

        if ($response->successful()) {
            return $response->json();
        }
        throw new \Exception($response->json('error', 'Verification failed.'), $response->status());
    }

    public function refund(string $transactionId): array
    {
        $response = $this->httpClient()->post("{$this->apiUrl}/refund", [
            'transaction_id' => $transactionId,
        ]);

        if ($response->successful()) {
            return $response->json();
        }
        throw new \Exception($response->json('error', 'Refund failed.'), $response->status());
    }
}
```

---

## 6. Database Schema

**Migration for `payments` table:**
```php
$table->string('gateway_transaction_id', 64)->nullable()->index();
```

**Model `Payment`** – Keep the column as a plain string; no casting needed.

---

## 7. Integration Workflow

### 7.1 Initiate Checkout

```php
use App\Services\PaymenterService;

public function processCheckout(Request $request, PaymenterService $paymenter)
{
    $amount = 1500; // Example: from cart
    $currency = config('services.paymenter.currency');
    $userEmail = auth()->user()->email;
    $callbackUrl = route('payment.callback'); // Named route for the callback

    $result = $paymenter->createSession($amount, $currency, $userEmail, $callbackUrl);

    // Store a Payment record with status 'pending' and a reference (e.g., order ID)
    Payment::create([
        'user_id'                => auth()->id(),
        'order_id'               => $order->id, // or whatever your business entity is
        'amount'                 => $amount,
        'currency'               => $currency,
        'status'                 => PaymentStatus::PENDING,
        'gateway_transaction_id' => null, // will be filled later
    ]);

    return redirect($result['payment_url']);
}
```

### 7.2 Handle the Gateway Callback

The gateway redirects back with query parameters:
- `transaction_id` (hex string)
- `gateway_status` (e.g., `Pending`)
- `ref` (your custom reference)

**Important:** This route only redirects to the frontend; business logic fulfillment is done via webhooks.

```php
public function handleCallback(Request $request)
{
    $transactionId = $request->query('transaction_id'); // hex string
    $ref = $request->query('ref');

    // Find your business entity by $ref (e.g., order, subscription)
    $order = Order::where('transaction_ref', $ref)->firstOrFail();

    // Update or create the Payment record with the transaction ID
    $payment = Payment::updateOrCreate(
        ['order_id' => $order->id, 'gateway_transaction_id' => null],
        [
            'gateway_transaction_id' => $transactionId,
            'status'                => PaymentStatus::PENDING,
        ]
    );

    return redirect(config('app.frontend_url') . "/payment-result?transaction_id={$transactionId}");
}
```

### 7.3 Webhooks (Async Business Fulfillment)

**Webhook route must be public (no authentication middleware).** Security relies entirely on HMAC signature verification.

**Webhook Headers:**
- `X-Paymenter-Signature: sha256=<hex_signature>`
- `X-Paymenter-Event: payment.completed` (or `payment.failed`, `payment.refunded`)

**Payload (JSON):**
```json
{
    "event": "payment.completed",
    "transaction_id": "b2ae55eba7704feeac0b9e4c69b0285b",
    "amount": "1500.00",
    "currency": "USD"
}
```

**Webhook Controller:**
```php
class WebhookController extends Controller
{
    public function handlePaymenter(Request $request)
    {
        // 1. Verify HMAC signature
        $signature = $request->header('X-Paymenter-Signature');
        $payload = $request->getContent();
        $computed = 'sha256=' . hash_hmac('sha256', $payload, config('services.paymenter.webhook_secret'));

        if (!hash_equals($signature, $computed)) {
            abort(401, 'Invalid signature');
        }

        $data = json_decode($payload, true);
        $transactionId = $data['transaction_id'];

        $payment = Payment::where('gateway_transaction_id', $transactionId)->firstOrFail();

        // 2. Idempotency check – only act if payment is still pending
        if ($payment->status === PaymentStatus::PENDING) {
            match ($data['event']) {
                'payment.completed' => $this->completePayment($payment),
                'payment.failed'    => $this->failPayment($payment),
                'payment.refunded'  => $this->refundPayment($payment),
                default             => null,
            };
        }

        return response()->json(['status' => 'success']);
    }
}
```

**Webhook route registration (outside any auth group):**
```php
// routes/api.php
Route::post('webhooks/paymenter', [WebhookController::class, 'handlePaymenter']);
```

### 7.4 Refunds (Admin-Initiated)

Only initiate the refund API call; the database update is handled by the `payment.refunded` webhook.

```php
public function processRefund(Order $order, PaymenterService $paymenter)
{
    $payment = $order->payment;
    $paymenter->refund($payment->gateway_transaction_id);
    // No DB change here – wait for webhook
}
```

---

## 8. Payment Verification Endpoint & Absolute Deadline

For client-side polling, you need a dedicated verification endpoint that returns the current payment status **plus an absolute deadline**.  
This endpoint belongs in a **PaymentController**, not a SubscriptionController.

**Backend endpoint example:**
```php
// routes/api.php (inside auth group if the user must be authenticated)
Route::get('payments/verify/{transactionId}', [PaymentController::class, 'verify'])
    ->where('transactionId', '^[0-9a-f]{32}$');
```

**Controller method:**
```php
public function verify(string $transactionId): JsonResponse
{
    $payment = Payment::where('gateway_transaction_id', $transactionId)->first();

    if (!$payment) {
        return response()->json(['message' => 'Payment not found.'], 404);
    }

    // Deadline: 15 minutes after the payment record was created (configurable)
    $deadline = $payment->created_at->addMinutes(15)->toIso8601String();

    return response()->json([
        'data' => [
            'status'   => $payment->status->value,
            'deadline' => $deadline,
            'payment'  => [
                'gateway_transaction_id' => $payment->gateway_transaction_id,
                'status'                 => $payment->status->value,
                'amount'                 => $payment->amount,
                'paid_at'                => $payment->paid_at?->toIso8601String(),
                'created_at'             => $payment->created_at->toIso8601String(),
            ],
            // Include any related resources as needed (order, subscription, etc.)
        ],
    ]);
}
```

**Response contract (JSON):**
```json
{
    "data": {
        "status": "pending",
        "deadline": "2026-07-23T16:18:00.000000Z",
        "payment": {
            "gateway_transaction_id": "b2ae55eba7704feeac0b9e4c69b0285b",
            "status": "pending",
            "amount": "9.99",
            "paid_at": null,
            "created_at": "2026-07-23T16:03:00.000000Z"
        }
    }
}
```

The `deadline` is an absolute timestamp, enabling the frontend to compute a countdown that survives page refreshes.

---

## 9. Smart Polling Guidelines (Frontend)

The frontend should poll the `/api/payments/verify/{transactionId}` endpoint.  
Key implementation rules:

- **Start polling immediately** with an interval of 3 seconds.
- **Stop polling** as soon as `data.status` is `success`, `failed`, or `refunded`.
- **Compute the countdown** using the `deadline` field: `timeLeft = max(0, deadline - now)`. Update every second.
- **When `timeLeft` reaches zero**, display a timeout UI and stop polling. Do **not** retry; direct the user back to a safe page.
- **Never hardcode a countdown duration** (e.g., 20 seconds). The backend is the source of truth.
- For the countdown ring's total duration, use `deadline - payment.created_at` so the progress bar remains accurate even if the page is loaded late.

Example pseudo-logic:
```
on mount: fetch initial status
every 3 seconds: refetch if status is 'pending'
every 1 second: update timeLeft = max(0, deadline - Date.now())
if timeLeft <= 0: show timeout, stop polling
if status is terminal: show result, stop polling
```

---

## 10. Simulator Reality Check

1. **Laravel calls `/api/pay`** → returns `token` and `payment_url`.
2. **User is redirected** to the Paymenter gateway.
3. **User enters card details** and requests OTP → OTP sent to email (check SMTP sink).
4. **User submits OTP** → funds held, Paymenter redirects back with `transaction_id` and `gateway_status=Pending`.
5. **Manual action:** In Paymenter admin, click **[Complete]** or **[Fail]**.
6. **Receipts** sent automatically.
7. **Webhook fires** with final status and HMAC signature.
8. **Polling** picks up the final status via `/api/verify/{transaction_id}` and stops.