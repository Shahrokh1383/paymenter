# Paymenter Gateway: Laravel Integration Guide (Hosted Payment Page)

**Version 2.0 – UUID transaction IDs**  
**Paymenter version:** 1.0+ with the above fixes applied.

---

## 1. Prerequisites

1.  **Local SMTP Sink:** Start your `smtp-server` project on port `1025` to intercept OTPs and Receipts.
2.  **Paymenter Dashboard:** Start Paymenter (defaults to `http://127.0.0.1:5000`).
3.  **Active Currency & Merchant:** Create a currency (e.g., `IRR`) and a Merchant in the Paymenter Dashboard.
4.  **Copy API Key:** Copy the Merchant's API Key.
5.  **Test User Account:** Create a User in Paymenter and Topup their balance so they can pay.

---

## 2. Laravel Configuration

**.env**
```env
PAYMENTER_API_URL=http://127.0.0.1:5000/api
PAYMENTER_API_KEY=your_api_key_here
PAYMENTER_CURRENCY=USD
```

**config/services.php**
```php
'paymenter' => [
    'url' => env('PAYMENTER_API_URL'),
    'key' => env('PAYMENTER_API_KEY'),
    'currency' => env('PAYMENTER_CURRENCY', 'USD'),
],
```

---

## 3. Paymenter Service Class

Create `app/Services/PaymenterService.php`.  
**Important:** `verify()` and `refund()` now expect `string` transaction IDs.

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

## 4. Database Schema

**Migration for `payments` table:**
```php
$table->string('gateway_transaction_id', 64)->nullable();
```

**Model `Payment`** – No cast needed for this column (it will be a string).

---

## 5. Integration Workflow

### 5.1 Initiate Checkout

```php
use App\Services\PaymenterService;

public function processCheckout(Request $request, PaymenterService $paymenter)
{
    $amount = 1500; // Example: Get from cart
    $currency = config('services.paymenter.currency');
    $userEmail = auth()->user()->email;
    $callbackUrl = route('checkout.callback');

    // Define where Paymenter should send the user after they enter their Card & OTP
    $result = $paymenter->createSession($amount, $currency, $userEmail, $callbackUrl);
    return redirect($result['payment_url']);
}
```

### 5.2 Handle the Gateway Callback

The gateway redirects the user back with:
- `transaction_id` (UUID string)
- `gateway_status` (e.g., `Pending`)
- `ref` (your custom reference)

```php
public function handleCallback(Request $request)
{
    $transactionId = $request->query('transaction_id'); // string
    $ref = $request->query('ref');

    // Find your subscription or order by $ref
    $payment = Payment::where('gateway_transaction_id', $transactionId)->firstOrNew();
    $payment->gateway_transaction_id = $transactionId;
    $payment->status = PaymentStatus::PENDING;
    $payment->save();

    return redirect("{$frontendUrl}/payment-result?transaction_id={$transactionId}");
}
```

### 5.3 Poll for Settlement (AJAX)

Create an endpoint that your frontend polls:

```php
public function pollStatus(Request $request, PaymenterService $paymenter)
{
    $transactionId = $request->input('transaction_id'); // string
    $result = $paymenter->verify($transactionId);

    // $result['status'] can be: 'Pending', 'Success', 'Failed', 'Refunded'
    if ($result['status'] === 'Success') {
        // Fulfill the order
    }
    return response()->json($result);
}
```

### 5.4 Processing Refunds (Admin Panel)

If you trigger a refund from your Laravel admin panel, Paymenter will process it and **automatically email a Refund Receipt** to the customer.

```php
public function processRefund($orderId, PaymenterService $paymenter)
{
    $order = Order::findOrFail($orderId);
    $paymenter->refund($order->payment_transaction_id); // string
    // Update order status
}
```

---

## 6. Simulator Reality Check

1. **Laravel calls `/api/pay`** → returns `token` and `payment_url`. No OTP yet.
2. **User is redirected** to the Paymenter gateway page.
3. **User enters card** and clicks “Request OTP” → OTP sent to the cardholder’s registered email (check your SMTP sink).
4. **User submits OTP** → Paymenter holds funds and redirects back with `transaction_id` (UUID string) and `gateway_status=Pending`.
5. **Manual step:** In Paymenter admin dashboard, click **[Complete]** to settle, or **[Fail]** to reject.
6. **Receipts** are automatically sent to the cardholder’s email.
7. **Your polling** picks up the final status via `/api/verify/{transaction_id}`.

---

## 7. Important Notes

- **Always treat `transaction_id` as a string** in your Laravel code and database.
- The Paymenter API `verify` and `refund` endpoints now accept and return string IDs.
- The callback URL receives the same UUID string; do not cast it to integer.
