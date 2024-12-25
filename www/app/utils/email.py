"""Utility functions for sending emails to users."""

import argparse
import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from www.settings import settings

logger = logging.getLogger(__name__)


async def send_email(subject: str, body: str, to: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email.sender_name} <{settings.email.sender_email}>"
    msg["To"] = to

    msg.attach(MIMEText(body, "html"))

    smtp_client = aiosmtplib.SMTP(hostname=settings.email.host, port=settings.email.port)

    await smtp_client.connect()
    await smtp_client.login(settings.email.username, settings.email.password)
    await smtp_client.sendmail(settings.email.sender_email, to, msg.as_string())
    await smtp_client.quit()


def test_email_adhoc() -> None:
    parser = argparse.ArgumentParser(description="Test sending an email.")
    parser.add_argument("subject", help="The subject of the email.")
    parser.add_argument("body", help="The body of the email.")
    parser.add_argument("to", help="The recipient of the email.")
    args = parser.parse_args()

    asyncio.run(send_email(args.subject, args.body, args.to))


if __name__ == "__main__":
    # python -m store.app.utils.email
    test_email_adhoc()
