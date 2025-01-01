"""Utility functions for sending emails to users."""

import argparse
import asyncio
import logging
import textwrap
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


async def send_delete_email(email: str) -> None:
    """Send an email notification when a user's account is deleted.

    Args:
        email: The email address of the user whose account was deleted.
    """
    body = textwrap.dedent(
        """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px;">K-Scale Labs</h1>
            <h2 style="color: #666;">Your account has been deleted</h2>
            <p style="color: #444; line-height: 1.6;">
                We're sorry to see you go. Your account and associated data have been successfully deleted from our
                system.
            </p>
            <p style="color: #444; line-height: 1.6;">
                If you have any questions or if this was done in error, please contact our support team.
            </p>
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px;">
                <p>This is an automated message, please do not reply directly to this email.</p>
            </div>
        </div>
        """
    )
    await send_email(subject="Account Deleted - K-Scale Labs", body=body, to=email)


async def send_signup_notification_email(email: str) -> None:
    """Send a welcome email notification when a user signs up via OAuth.

    Args:
        email: The email address of the newly registered user.
    """
    body = textwrap.dedent(
        """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px;">K-Scale Labs</h1>
            <h2 style="color: #666;">Welcome to K-Scale Labs!</h2>
            <p style="color: #444; line-height: 1.6;">
                Thank you for joining our community. Your account has been successfully created using OAuth
                authentication.
            </p>
            <p style="color: #444; line-height: 1.6;">
                We're excited to have you on board and look forward to helping you make the most of our services.
            </p>
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px;">
                <p>This is an automated message, please do not reply directly to this email.</p>
            </div>
        </div>
        """
    )
    await send_email(subject="Welcome to K-Scale Labs", body=body, to=email)


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
