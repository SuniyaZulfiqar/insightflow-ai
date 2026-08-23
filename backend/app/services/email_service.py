"""Sends account verification codes over email.

Uses Gmail's SMTP server with an App Password when GMAIL_ADDRESS and
GMAIL_APP_PASSWORD are configured in the environment. When they are not
configured (e.g. local development), the code is printed to the server
console instead so registration still works end-to-end without real
email credentials.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_verification_email(to_email: str, name: str, code: str) -> None:
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        print(f"[DEV] Verification code for {to_email}: {code}")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = "Your InsightFlow verification code"
    message["From"] = settings.GMAIL_ADDRESS
    message["To"] = to_email

    text_body = (
        f"Hi {name},\n\n"
        f"Your InsightFlow verification code is: {code}\n\n"
        "This code expires in 15 minutes. If you didn't request this, "
        "you can safely ignore this email.\n"
    )

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#172554;">InsightFlow</h2>
      <p>Hi {name},</p>
      <p>Your verification code is:</p>
      <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px; color:#0f766e;">{code}</p>
      <p style="color:#64748b; font-size: 13px;">
        This code expires in 15 minutes. If you didn't request this, you can
        safely ignore this email.
      </p>
    </div>
    """

    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_ADDRESS, to_email, message.as_string())
    except Exception as exc:
        # Never let an email delivery failure break registration/login flows.
        print(f"[WARN] Failed to send verification email to {to_email}: {exc}")
        print(f"[DEV] Verification code for {to_email}: {code}")
