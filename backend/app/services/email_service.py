import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, body: str, is_html: bool = False):
        """Generic method to send an email via SMTP."""
        if not settings.SMTP_HOST:
            logger.warning("SMTP_HOST not configured. Email not sent.")
            return False

        message = MIMEMultipart()
        message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject

        part = MIMEText(body, "html" if is_html else "plain")
        message.attach(part)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_reset_password_email(email: str, token: str):
        """Send a password reset link to the user."""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Reset Kata Sandi SAR-BOT"
        
        body_html = f"""
        <html>
        <body>
            <p>Halo,</p>
            <p>Anda menerima email ini karena kami menerima permintaan untuk mereset kata sandi akun SAR-BOT Anda.</p>
            <p>Silakan klik tautan di bawah ini untuk mereset kata sandi Anda:</p>
            <p><a href="{reset_link}" style="display:inline-block; padding:10px 20px; background-color:#ef4444; color:white; text-decoration:none; rounded:5px;">Reset Kata Sandi</a></p>
            <p>Atau salin dan tempel tautan berikut di browser Anda:</p>
            <p>{reset_link}</p>
            <p>Tautan ini akan kedaluwarsa dalam 1 jam. Jika Anda tidak merasa meminta reset kata sandi, abaikan email ini.</p>
            <p>Terima kasih,<br>Tim SAR-BOT</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(email, subject, body_html, is_html=True)

email_service = EmailService()
