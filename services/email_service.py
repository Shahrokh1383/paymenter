import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
FROM_EMAIL = "PaymwnterServerTeam@gmail.com"

def send_otp_email(to_email: str, otp_code: str, merchant_name: str, amount: float, currency_code: str):
    """Dispatches the OTP email to the local SMTP sink."""
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = f"Your Paymenter Verification Code"

    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Payment Verification Required</h2>
            <p>You are attempting to make a payment of <strong>{amount} {currency_code}</strong> to <strong>{merchant_name}</strong>.</p>
            <p>Please use the following One-Time Password (OTP) to authorize this transaction on the secure gateway page:</p>
            <h1 style="background-color: #f4f4f4; padding: 15px; text-align: center; letter-spacing: 5px; border-radius: 5px;">{otp_code}</h1>
            <p>If you did not initiate this transaction, please ignore this email.</p>
            <hr>
            <p style="font-size: 12px; color: #777;">This is an automated message from your local Paymenter simulator.</p>
        </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg)
        print(f"[EMAIL DISPATCH] OTP sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL DISPATCH ERROR] Failed to send OTP: {e}")

def send_receipt_email(to_email: str, status: str, amount: float, currency_code: str, merchant_name: str):
    """Dispatches the final transaction receipt email."""
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    
    if status == "Success":
        msg['Subject'] = "Payment Receipt - Successful"
        color = "#28a745"
        message = f"Your payment of {amount} {currency_code} to {merchant_name} was successfully completed."
    else:
        msg['Subject'] = "Payment Notice - Refunded/Failed"
        color = "#dc3545"
        message = f"Your payment of {amount} {currency_code} to {merchant_name} was {status}. The funds have been returned to your account."

    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: {color};">Transaction {status}</h2>
            <p>{message}</p>
            <hr>
            <p style="font-size: 12px; color: #777;">This is an automated message from your local Paymenter simulator.</p>
        </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg)
        print(f"[EMAIL DISPATCH] Receipt ({status}) sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL DISPATCH ERROR] Failed to send receipt: {e}")