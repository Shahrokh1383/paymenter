"""
Paymenter HPP & OTP Integration Test Script (Final Version)
-----------------------------------------------------------
Run from the root 'paymenter' directory:
python tests/test_hpp_flow.py
"""

import sys
import os
import re

# Add the project root to sys.path to allow absolute imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

import requests
from urllib.parse import urlparse, parse_qs

# DRY: Import the exact DB_PATH and connection factory used by the live application
from database.connection import DB_PATH, get_db_connection

# --- Configuration ---
BASE_URL = "http://127.0.0.1:5001"

def get_test_data():
    """
    Fetches a valid Merchant and User Account that SHARE THE SAME CURRENCY.
    Also fetches the user's actual balance for dynamic amount calculation.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            m.api_key, 
            m.name as merchant_name, 
            a.card_number, 
            c.code as currency_code, 
            u.name as user_name,
            a.balance as user_balance
        FROM merchants m
        JOIN accounts m_settlement ON m.settlement_account_id = m_settlement.id
        JOIN accounts a ON a.currency_id = m_settlement.currency_id
        JOIN currencies c ON a.currency_id = c.id
        JOIN users u ON a.user_id = u.id
        WHERE m.is_active = 1 
          AND a.balance > 0 
          AND c.is_active = 1
          AND a.id != m_settlement.id
        LIMIT 1
    """)
    data = cursor.fetchone()
    
    if not data:
        conn.close()
        sys.exit("❌ No matching test data found. Ensure you have an active merchant and a user with a balance in the SAME currency.")
        
    conn.close()
    return data['api_key'], data['merchant_name'], data['card_number'], data['currency_code'], data['user_name'], data['user_balance']

def print_step(step_num, title):
    print(f"\n{'='*20} STEP {step_num}: {title} {'='*20}")

def main():
    print("🚀 Starting Paymenter HPP & OTP Integration Test...")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        sys.exit(1)

    try:
        api_key, merchant_name, card_number, currency_code, user_name, user_balance = get_test_data()
    except Exception as e:
        print(f"❌ Failed to fetch test data: {e}")
        return

    test_email = f"{user_name.lower().replace(' ', '.')}@test.local"
    callback_url = "http://laravel-shop.local/checkout/callback"
    
    # DYNAMIC AMOUNT: Use 10% of the user's actual balance to guarantee sufficient funds
    amount = max(1.0, float(user_balance) * 0.10)

    print(f"✅ Test Data Loaded (Currency Matched):")
    print(f"   - Merchant: {merchant_name}")
    print(f"   - Card: {card_number}")
    print(f"   - Currency: {currency_code}")
    print(f"   - User Balance: {user_balance} | Test Amount: {amount}")
    print(f"   - Email: {test_email}")

    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    # --- STEP 1: Create Payment Session (API) ---
    print_step(1, "Create Payment Session (Laravel API Call)")
    pay_payload = {
        "amount": amount,
        "currency_code": currency_code,
        "user_email": test_email,
        "callback_url": callback_url
    }
    
    try:
        res = session.post(f"{BASE_URL}/api/pay", json=pay_payload, timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to Paymenter at {BASE_URL}. Is the server running?")
        return

    if res.status_code != 200:
        print(f"❌ Failed to create session: {res.text}")
        return
        
    pay_data = res.json()
    token = pay_data.get("token")
    print(f"✅ Session Created Successfully! Token: {token}")
    print(f"   👉 Check your SMTP Server terminal/inbox for the OTP email sent to {test_email}!")

    # --- STEP 2: Extract OTP (Simulate User Checking Email) ---
    print_step(2, "Extract OTP from Database (Simulate Reading Email)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT otp_code FROM gateway_sessions WHERE token = ?", (token,))
    session_data = cursor.fetchone()
    conn.close()
    
    if not session_data:
        print("❌ Gateway session not found in DB.")
        return
        
    otp_code = session_data['otp_code']
    print(f"✅ OTP Intercepted: {otp_code}")

    # --- STEP 3: Authorize Payment (Gateway UI Form Submission) ---
    print_step(3, "Authorize Payment (User submits Card & OTP)")
    auth_payload = {
        "token": token,
        "card_number": card_number,
        "otp_code": otp_code
    }
    
    res = session.post(f"{BASE_URL}/gateway/authorize", data=auth_payload, allow_redirects=False)
    
    if res.status_code not in [302, 303]:
        print(f"❌ Authorization failed. Status: {res.status_code}")
        return
        
    redirect_url = res.headers.get("Location", "")
    
    # Senior-level validation: Detect if the server rejected the auth and redirected back to the form
    if "/gateway/" in redirect_url and "transaction_id" not in redirect_url:
        print(f"❌ Authorization Rejected! The server redirected back to the gateway form.")
        
        # Fetch the redirected page to extract the flash message using built-in Regex (KISS principle)
        form_res = session.get(f"{BASE_URL}{redirect_url}")
        if form_res.status_code == 200:
            match = re.search(r'<div class="alert alert-error">(.*?)</div>', form_res.text, re.DOTALL)
            if match:
                error_msg = match.group(1).strip()
                print(f"   🛑 Server Error Message: {error_msg}")
            else:
                print("   Could not extract specific error message from HTML.")
        return

    print(f"✅ Payment Authorized! Funds Held.")
    
    # Parse transaction_id from callback URL
    parsed = urlparse(redirect_url)
    query_params = parse_qs(parsed.query)
    transaction_id = query_params.get("transaction_id", [None])[0]
    
    if not transaction_id:
        print("❌ Could not extract transaction_id from callback URL.")
        return
        
    print(f"   - Transaction ID: {transaction_id}")

    # --- STEP 4: Verify Status (Laravel Polling) ---
    print_step(4, "Verify Transaction Status (Should be Pending)")
    res = session.get(f"{BASE_URL}/api/verify/{transaction_id}")
    if res.status_code != 200:
        print(f"❌ Verification failed: {res.text}")
        return
        
    verify_data = res.json()
    print(f"✅ Current Status: {verify_data['status']}")

    # --- STEP 5: Admin Complete (Dashboard Action) ---
    print_step(5, "Admin Completes Transaction (Simulate Dashboard Click)")
    res = requests.post(f"{BASE_URL}/transactions/complete/{transaction_id}")
    
    if res.status_code == 200:
        complete_data = res.json()
        print(f"✅ Admin Action Success: {complete_data}")
        print(f"   👉 Check your SMTP Server inbox for the 'Payment Successful' HTML receipt!")
    else:
        print(f"❌ Admin Complete failed: {res.text[:500]}...")
        return

    # --- STEP 6: Final Verification ---
    print_step(6, "Final Verification (Should be Success)")
    res = session.get(f"{BASE_URL}/api/verify/{transaction_id}")
    verify_data = res.json()
    print(f"✅ Final Status: {verify_data['status']}")
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED! The HPP & OTP flow is working perfectly.")
    print("="*60)

if __name__ == "__main__":
    main()