import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
FROM_EMAIL = "PaymwnterServerTeam@gmail.com"

class SmtpAdapter(NotificationDispatcher):
    """Infrastructure adapter for SMTP. Replaces legacy email_service."""
    
    def send_receipt(self, to_email: str, status: str, amount: float, currency_code: str, merchant_name: str) -> None:
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