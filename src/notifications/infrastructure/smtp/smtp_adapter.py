import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.notifications.domain.ports.notification_dispatcher_port import NotificationDispatcher
from src.common.domain.value_objects.money import Money
from src.common.domain.value_objects.email_address import EmailAddress

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
FROM_EMAIL = "PaymwnterServerTeam@gmail.com"

class SmtpAdapter(NotificationDispatcher):
    """Infrastructure adapter for SMTP. Replaces legacy email_service."""
    
    def send_receipt(self, to_email: EmailAddress, status: str, amount: Money, merchant_name: str, remaining_balance: Money) -> None:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email.value
        
        if status == "Success":
            msg['Subject'] = "Payment Receipt - Successful"
            color = "#28a745"
            message = f"Your payment of {amount.amount} {amount.currency.value} to {merchant_name} was successfully completed."
        else:
            msg['Subject'] = "Payment Notice - Refunded/Failed"
            color = "#dc3545"
            message = f"Your payment of {amount.amount} {amount.currency.value} to {merchant_name} was {status}. The funds have been returned to your account."

        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: {color};">Transaction {status}</h2>
                <p>{message}</p>
                <p style="margin-top: 15px; font-size: 14px; background-color: #f8f9fa; padding: 10px; border-radius: 5px;">
                    Your remaining account balance is: <strong style="color: #0056b3;">{remaining_balance.amount} {remaining_balance.currency.value}</strong>
                </p>
                <hr>
                <p style="font-size: 12px; color: #777;">This is an automated message from your local Paymenter simulator.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        self._dispatch_email(msg, to_email.value, f"Receipt ({status})")

    def send_otp(self, to_email: EmailAddress, otp_code: str, merchant_name: str, amount: Money) -> None:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email.value
        msg['Subject'] = f"Your OTP Code for {merchant_name} Payment"

        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #007bff;">Payment Verification</h2>
                <p>You are initiating a payment of <strong>{amount.amount} {amount.currency.value}</strong> to <strong>{merchant_name}</strong>.</p>
                <p>Your One-Time Password (OTP) is:</p>
                <h1 style="background-color: #f4f4f4; padding: 10px; text-align: center; letter-spacing: 5px; color: #333;">{otp_code}</h1>
                <p>This code will expire shortly. Please do not share it with anyone.</p>
                <hr>
                <p style="font-size: 12px; color: #777;">This is an automated message from your local Paymenter simulator.</p>
            </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))
        self._dispatch_email(msg, to_email.value, "OTP")

    def _dispatch_email(self, msg: MIMEMultipart, to_email: str, email_type: str) -> None:
        """Internal helper to handle the actual SMTP connection and sending."""
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.send_message(msg)
            print(f"[EMAIL DISPATCH] {email_type} sent to {to_email}")
        except Exception as e:
            print(f"[EMAIL DISPATCH ERROR] Failed to send {email_type}: {e}")
            raise e