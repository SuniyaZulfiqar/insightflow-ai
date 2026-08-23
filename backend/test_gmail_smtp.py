"""Standalone Gmail SMTP credential test.

Run this from your backend project root (same place as uvicorn):

    python test_gmail_smtp.py

It prints exactly what's in your .env for these two variables (password
partially masked) and tries to log in to Gmail's SMTP server directly,
so we can tell immediately whether the credentials themselves are the
problem, separate from the rest of the app.
"""

import smtplib

from app.config import settings

address = settings.GMAIL_ADDRESS
password = settings.GMAIL_APP_PASSWORD

print(f"GMAIL_ADDRESS from .env: {address!r}")
print(f"GMAIL_APP_PASSWORD length: {len(password)} characters")
print(f"GMAIL_APP_PASSWORD contains spaces: {' ' in password}")
print(f"GMAIL_APP_PASSWORD preview: {password[:2]}...{password[-2:]}" if password else "GMAIL_APP_PASSWORD is empty")
print()

if not address or not password:
    print("One or both variables are empty. Check that .env is in this folder "
          "and the variable names match exactly: GMAIL_ADDRESS, GMAIL_APP_PASSWORD")
else:
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(address, password)
        print("SUCCESS: Gmail accepted the credentials.")
    except smtplib.SMTPAuthenticationError as exc:
        print(f"FAILED: Gmail rejected the credentials.\n{exc}")
    except Exception as exc:
        print(f"FAILED: Unexpected error.\n{exc}")
