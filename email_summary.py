import html
import os
from datetime import datetime

import keyring
import resend

from daily_summary import build_daily_summary

from database import (
    get_daily_summary_recipient,
    get_daily_summary_sender,
)


KEYRING_SERVICE = "ao3-stat-dashboard"
KEYRING_USERNAME = "resend_api_key"


def get_resend_config():
    # Environment variable remains useful
    # for temporary/manual development.
    api_key = os.environ.get(
        "RESEND_API_KEY"
    )

    # For unattended Windows operation,
    # retrieve the secret from Credential
    # Locker if no environment variable exists.
    if not api_key:
        api_key = keyring.get_password(
            KEYRING_SERVICE,
            KEYRING_USERNAME,
        )

    sender = (
        get_daily_summary_sender()
    )

    if not api_key:
        raise RuntimeError(
            "Resend API key was not found "
            "in the environment or Windows "
            "Credential Locker."
        )

    if not sender:
        raise RuntimeError(
            "Daily summary sender "
            "has not been configured."
        )

    return {
        "api_key": api_key,
        "sender": sender,
    }


def send_daily_summary_email():
    recipient = (
        get_daily_summary_recipient()
    )

    if not recipient:
        raise RuntimeError(
            "Daily summary recipient "
            "has not been configured."
        )

    config = get_resend_config()

    resend.api_key = config[
        "api_key"
    ]

    summary = build_daily_summary()

    local_now = datetime.now(
    ).astimezone()

    subject = (
        "AO3 Daily Stats Summary — "
        + local_now.strftime(
            "%b %d, %Y"
        )
    )

    html_summary = html.escape(
        summary
    )

    html_body = f"""
    <html>
        <body>
            <pre style="
                font-family:
                    Arial,
                    sans-serif;
                white-space: pre-wrap;
                line-height: 1.5;
            ">{html_summary}</pre>
        </body>
    </html>
    """

    params = {
        "from": config["sender"],
        "to": [
            recipient
        ],
        "subject": subject,
        "html": html_body,
        "text": summary,
    }

    try:
        result = resend.Emails.send(
            params
        )

    except Exception as error:
        raise RuntimeError(
            "Resend email delivery "
            f"failed: {error}"
        ) from error

    email_id = None

    if isinstance(result, dict):
        email_id = result.get(
            "id"
        )

    else:
        email_id = getattr(
            result,
            "id",
            None,
        )

    return {
        "recipient": recipient,
        "subject": subject,
        "email_id": email_id,
    }