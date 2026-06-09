
---

# Paymenter Gateway: Laravel Integration Guide

This document provides a complete, production-like workflow for integrating a Laravel application with the Paymenter Payment Gateway simulator. It covers initiating payments, verifying transaction statuses, and handling refunds.

## 1. Prerequisites in Paymenter Dashboard

Before writing any Laravel code, ensure the following are set up in your Paymenter Dashboard (defaults to `http://127.0.0.1:5000`, but check your Paymenter terminal for the dynamically assigned port if 5000 is busy):

1.  **Active Currency:** Create a currency (e.g., Code: `IRR`, Name: `Toman`).
2.  **Merchant Account:** Create a Merchant (e.g., "Laravel Shop").
3.  **Merchant Settlement Account:** Ensure the merchant has a settlement account in the desired currency. *(Note: When you create a merchant via the dashboard, a settlement account is auto-generated. Ensure its currency is set correctly).*
4.  **Copy API Key:** Copy the Merchant's API Key. You will need this for Laravel.
5.  **Test User Account:** Create a User, give them an Account, and Topup their balance so they can pay.

## 2. Laravel Configuration

First, configure your Laravel environment to communicate with Paymenter.

**Update `.env` file:**
Add the following variables to your Laravel project's `.env` file. This adheres to the DRY principle and keeps credentials out of version control.

```env
# IMPORTANT: Paymenter dynamically allocates a port starting from 5000. 
# If port 5000 is already in use, it will automatically start on 5001, 5002, etc.
# Always verify the port shown in your Paymenter terminal and update this URL accordingly.
PAYMENTER_API_URL=http://127.0.0.1:5000/api
PAYMENTER_API_KEY=your_copied_merchant_api_key_here
```

**Update `config/services.php`:**
Publish the environment variables to Laravel's config system.

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

To adhere to SRP (Single Responsibility Principle), we will create a dedicated Service class that handles all HTTP communications with Paymenter. This keeps your controllers thin and your API logic centralized.

**Create `app/Services/PaymenterService.php`:**

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Http\Client\RequestException;

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
     * Initiate a payment (Hold Funds)
     */
    public function pay(string $cardNumber, float $amount, string $currencyCode)
    {
        $response = Http::withHeaders([
            'x-api-key' => $this->apiKey,
        ])->post("{$this->apiUrl}/pay", [
            'destination_card_number' => $cardNumber,
            'amount'                  => $amount,
            'currency_code'           => $currencyCode,
        ]);

        if ($response->successful()) {
            return $response->json(); // Contains 'transaction_id' and 'status' (Pending)
        }

        // Handle specific errors (e.g., 402 Insufficient Funds, 400 Bad Request)
        throw new \Exception($response->json('error', 'Payment initiation failed.'), $response->status());
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
            return $response->json(); // Contains transaction details
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
            return $response->json(); // Contains refund status
        }

        throw new \Exception($response->json('error', 'Refund failed.'), $response->status());
    }
}
```

## 4. Laravel Implementation Workflow

Now, let's use the Service class in a Controller to handle the e-commerce checkout flow.

### Step 1: Initiate Checkout (Controller)

When the user submits their card number on your checkout page, you call the `pay` method.

```php
<?php

namespace App\Http\Controllers;

use App\Services\PaymenterService;
use Illuminate\Http\Request;

class CheckoutController extends Controller
{
    public function processCheckout(Request $request, PaymenterService $paymenter)
    {
        $validated = $request->validate([
            'card_number' => 'required|string|size:16', // 16-digit card
        ]);

        $orderAmount = 150000; // Example: Get from cart
        $currencyCode = 'IRR'; 

        try {
            $result = $paymenter->pay(
                $validated['card_number'],
                $orderAmount,
                $currencyCode
            );

            // Payment is Pending! Save the transaction_id to your Order
            // Example: Order::where('id', $orderId)->update(['payment_transaction_id' => $result['transaction_id']]);

            return redirect()->route('checkout.waiting', ['transaction_id' => $result['transaction_id']]);

        } catch (\Exception $e) {
            // Handle errors like Insufficient Funds (402) or Invalid Card (400)
            return back()->withErrors(['payment' => $e->getMessage()]);
        }
    }
}
```

### Step 2: The "Waiting" or "Callback" View

Because this is a simulator, the payment stays `Pending` until you approve it in the Paymenter Dashboard. You can show a waiting page that uses AJAX or a form button to check the status.

**A simple route to check status:**

```php
public function checkStatus(Request $request, PaymenterService $paymenter)
{
    $transactionId = $request->input('transaction_id');

    try {
        $result = $paymenter->verify($transactionId);

        if ($result['status'] === 'Success') {
            // Payment is Complete! Finalize the order in your DB
            // Order::complete($transactionId);
            return response()->json(['status' => 'success', 'message' => 'Payment successful!']);
        }

        if ($result['status'] === 'Failed' || $result['status'] === 'Refunded') {
            // Payment failed
            return response()->json(['status' => 'failed', 'message' => 'Payment failed.']);
        }

        // Still Pending
        return response()->json(['status' => 'pending', 'message' => 'Waiting for gateway approval...']);

    } catch (\Exception $e) {
        return response()->json(['status' => 'error', 'message' => $e->getMessage()]);
    }
}
```

### Step 3: Processing Refunds (Admin Panel)

If a customer requests a refund from your Laravel admin panel, you simply call the refund method using the saved `transaction_id`.

```php
public function processRefund($orderId, PaymenterService $paymenter)
{
    $order = Order::findOrFail($orderId);

    if (!$order->payment_transaction_id) {
        return back()->withErrors(['refund' => 'No transaction ID found for this order.']);
    }

    try {
        $paymenter->refund($order->payment_transaction_id);
        
        // Update your Laravel DB that the order is refunded
        // $order->update(['status' => 'refunded']);

        return back()->with('success', 'Refund processed successfully. Funds are returning to the customer.');

    } catch (\Exception $e) {
        return back()->withErrors(['refund' => $e->getMessage()]);
    }
}
```

---

## The Simulator Reality Check (Important for Developers)

When testing your Laravel application with Paymenter, remember that the flow is slightly different from a real, automated bank:

1.  **Laravel sends `/api/pay`**: Paymenter deducts the user's balance and returns a `Pending` transaction.
2.  **MANUAL ACTION REQUIRED**: You (the developer) must open the Paymenter Dashboard (defaults to `http://127.0.0.1:5000/transactions`, but check your terminal for the active dynamic port), find the Pending transaction, and click **[Complete]** (simulating the bank's approval).
3.  **Laravel verifies `/api/verify`**: Once you click Complete, the next time your Laravel application calls the verify endpoint, Paymenter will return `Success`, and you can finalize the order in your Laravel database.

This architecture perfectly mimics the asynchronous nature of real-world payment gateways, giving you a robust environment to build and test your e-commerce logic!
```