import html
import os
from datetime import datetime

import resend

from daily_summary import build_daily_summary

from database import (
    get_daily_summary_recipient,
)


def get_resend_config():
    api_key = os.environ.get(
        "RESEND_API_KEY"
    )

    sender = os.environ.get(
        "AO3_RESEND_FROM"
    )

    missing = []

    if not api_key:
        missing.append(
            "RESEND_API_KEY"
        )

    if not sender:
        missing.append(
            "AO3_RESEND_FROM"
        )

    if missing:
        raise RuntimeError(
            "Missing Resend environment "
            "variable(s): "
            + ", ".join(missing)
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