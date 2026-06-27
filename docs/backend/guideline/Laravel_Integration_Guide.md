# Paymenter Gateway: Laravel Integration Guide (Hosted Payment Page)

This document provides a complete, production-like workflow for integrating a Laravel application with the Paymenter Payment Gateway simulator using the **Hosted Payment Page (HPP)** architecture. This ensures your Laravel application remains PCI-DSS compliant by never handling raw credit card numbers.

## 1. Prerequisites

Before writing any Laravel code, ensure the following are running and set up:

1.  **Local SMTP Sink:** Start your `smtp-server` project on port `1025` to intercept OTPs and Receipts.
2.  **Paymenter Dashboard:** Start Paymenter (defaults to `http://127.0.0.1:5000`).
3.  **Active Currency & Merchant:** Create a currency (e.g., `IRR`) and a Merchant in the Paymenter Dashboard.
4.  **Copy API Key:** Copy the Merchant's API Key.
5.  **Test User Account:** Create a User in Paymenter and Topup their balance so they can pay.

## 2. Laravel Configuration

**Update `.env` file:**
```env
# Verify the port shown in your Paymenter terminal
PAYMENTER_API_URL=http://127.0.0.1:5000/api
PAYMENTER_API_KEY=your_copied_merchant_api_key_here
```

**Update `config/services.php`:**
```php
return [
    // ... other services
    'paymenter' => [
        'url' => env('PAYMENTER_API_URL'),
        'key' => env('PAYMENTER_API_KEY'),
    ],
];
```

## 3. Creating the Payment Service Class

To adhere to SRP, we create a dedicated Service class. Notice that we **no longer send card numbers** to the API. We only send the intent data.

**Create `app/Services/PaymenterService.php`:**

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

    /**
     * Create a Payment Session (Intent)
     */
    public function createSession(float $amount, string $currencyCode, string $userEmail, string $callbackUrl)
    {
        $response = Http::withHeaders([
            'x-api-key' => $this->apiKey,
        ])->post("{$this->apiUrl}/pay", [
            'amount'        => $amount,
            'currency_code' => $currencyCode,
            'user_email'    => $userEmail,
            'callback_url'  => $callbackUrl,
        ]);

        if ($response->successful()) {
            return $response->json(); // Contains 'token' and 'payment_url'
        }

        throw new \Exception($response->json('error', 'Payment session creation failed.'), $response->status());
    }

    /**
     * Verify a transaction status
     */
    public function verify(int $transactionId)
    {
        $response = Http::withHeaders([
            'x-api-key' => $this->apiKey,
        ])->get("{$this->apiUrl}/verify/{$transactionId}");

        if ($response->successful()) {
            return $response->json();
        }

        throw new \Exception($response->json('error', 'Verification failed.'), $response->status());
    }

    /**
     * Refund a transaction
     */
    public function refund(int $transactionId)
    {
        $response = Http::withHeaders([
            'x-api-key' => $this->apiKey,
        ])->post("{$this->apiUrl}/refund", [
            'transaction_id' => $transactionId,
        ]);

        if ($response->successful()) {
            return $response->json();
        }

        throw new \Exception($response->json('error', 'Refund failed.'), $response->status());
    }
}
```

## 4. Laravel Implementation Workflow

### Step 1: Initiate Checkout (Controller)

When the user clicks "Checkout", you create a session and redirect them to the secure Paymenter Gateway.

```php
<?php

namespace App\Http\Controllers;

use App\Services\PaymenterService;
use Illuminate\Http\Request;

class CheckoutController extends Controller
{
    public function processCheckout(Request $request, PaymenterService $paymenter)
    {
        $orderAmount = 150000; // Example: Get from cart
        $currencyCode = 'IRR'; 
        $userEmail = 'testuser@example.com'; // Get from authenticated user
        
        // Define where Paymenter should send the user after they enter their Card & OTP
        $callbackUrl = route('checkout.callback'); 

        try {
            $result = $paymenter->createSession(
                $orderAmount, 
                $currencyCode, 
                $userEmail, 
                $callbackUrl
            );

            // Redirect user to the isolated Paymenter Gateway Page
            return redirect($result['payment_url']);

        } catch (\Exception $e) {
            return back()->withErrors(['payment' => $e->getMessage()]);
        }
    }
}
```

### Step 2: Handle the Gateway Callback

After the user enters their Card and OTP on the Paymenter Gateway, Paymenter redirects them back to your `callback_url` with the `transaction_id`.

```php
public function handleCallback(Request $request)
{
    $transactionId = $request->query('transaction_id');
    $gatewayStatus = $request->query('gateway_status'); // Usually 'Pending' awaiting admin approval

    if (!$transactionId) {
        return redirect()->route('checkout.failed')->withErrors('Payment canceled or failed.');
    }

    // Save the transaction_id to your Order model
    // Order::where('session_id', $sessionId)->update(['payment_transaction_id' => $transactionId, 'status' => 'awaiting_settlement']);

    // Show a "Waiting for Bank Approval" page to the user
    return view('checkout.waiting', ['transactionId' => $transactionId]);
}
```

### Step 3: Verification & Fulfillment (Webhook / Polling)

Because the Admin must manually click **[Complete]** in the simulator, your Laravel app should poll the `/api/verify` endpoint via AJAX, or you can simulate a Webhook.

```php
public function checkStatus(Request $request, PaymenterService $paymenter)
{
    $transactionId = $request->input('transaction_id');

    try {
        $result = $paymenter->verify($transactionId);

        if ($result['status'] === 'Success') {
            // Payment is Complete! Fulfill the order.
            // Note: Paymenter has also automatically emailed a Success Receipt to the user.
            return response()->json(['status' => 'success', 'message' => 'Payment successful!']);
        }

        if ($result['status'] === 'Failed' || $result['status'] === 'Refunded') {
            return response()->json(['status' => 'failed', 'message' => 'Payment failed.']);
        }

        return response()->json(['status' => 'pending', 'message' => 'Waiting for gateway settlement...']);

    } catch (\Exception $e) {
        return response()->json(['status' => 'error', 'message' => $e->getMessage()]);
    }
}
```

### Step 4: Processing Refunds (Admin Panel)

If you trigger a refund from your Laravel admin panel, Paymenter will process it and **automatically email a Refund Receipt** to the customer.

```php
public function processRefund($orderId, PaymenterService $paymenter)
{
    $order = Order::findOrFail($orderId);

    try {
        $paymenter->refund($order->payment_transaction_id);
        // $order->update(['status' => 'refunded']);
        return back()->with('success', 'Refund processed. Customer has been notified via email.');
    } catch (\Exception $e) {
        return back()->withErrors(['refund' => $e->getMessage()]);
    }
}
```

---

## The Simulator Reality Check (Important for Developers)

When testing your Laravel application with Paymenter, remember the exact flow:

1.  **Laravel creates Session**: Laravel calls `/api/pay`. Paymenter emails an OTP to the local SMTP sink.
2.  **User Authorization**: Laravel redirects the user to the `payment_url`. The user opens the SMTP Web UI, gets the OTP, and enters it + their Card Number on the Paymenter Gateway page.
3.  **Callback**: Paymenter holds the funds and redirects the user back to Laravel. The transaction is now `Pending`.
4.  **MANUAL ACTION REQUIRED**: You (the developer) must open the Paymenter Admin Dashboard, find the Pending transaction, and click **[Complete]** or **[Fail]**.
5.  **Automated Receipts**: The moment you click Complete/Fail, check your SMTP Web UI. A beautifully formatted HTML receipt has instantly arrived in the user's inbox!
```