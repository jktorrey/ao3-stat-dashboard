from datetime import (
    datetime,
    time,
    timezone,
)

from app_logging import (
    capture_output,
)

from tzlocal import get_localzone

from database import (
    initialize_database,
    get_daily_summary_recipient,
    get_daily_summary_time,
    get_last_daily_summary,
    set_last_daily_summary,
)

from email_summary import (
    send_daily_summary_email,
)


LOCAL_TIMEZONE = get_localzone()


def parse_timestamp(value):
    if not value:
        return None

    timestamp = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    return timestamp.astimezone(
        timezone.utc
    )


def get_scheduled_time_today(
    now_local,
    summary_time,
):
    hour_text, minute_text = (
        summary_time.split(
            ":",
            1,
        )
    )

    scheduled_clock = time(
        hour=int(hour_text),
        minute=int(minute_text),
    )

    return datetime.combine(
        now_local.date(),
        scheduled_clock,
        tzinfo=LOCAL_TIMEZONE,
    )


def daily_summary_is_due():
    recipient = (
        get_daily_summary_recipient()
    )

    summary_time = (
        get_daily_summary_time()
    )

    if not recipient:
        return (
            False,
            "Daily summary recipient is not configured.",
        )

    if not summary_time:
        return (
            False,
            "Daily summary delivery time is not configured.",
        )

    now_utc = datetime.now(
        timezone.utc
    )

    now_local = now_utc.astimezone(
        LOCAL_TIMEZONE
    )

    scheduled_today = (
        get_scheduled_time_today(
            now_local,
            summary_time,
        )
    )

    if now_local < scheduled_today:
        return (
            False,
            "Today's delivery time has not arrived yet.",
        )

    last_summary = (
        get_last_daily_summary()
    )

    if last_summary:
        last_summary_utc = (
            parse_timestamp(
                last_summary
            )
        )

        last_summary_local = (
            last_summary_utc.astimezone(
                LOCAL_TIMEZONE
            )
        )

        if (
            last_summary_local.date()
            == now_local.date()
        ):
            return (
                False,
                "Today's daily summary has already been sent.",
            )

    return (
        True,
        "Daily summary is due.",
    )


def send_summary_if_due():
    initialize_database()

    due, reason = (
        daily_summary_is_due()
    )

    print(reason)

    if not due:
        return False

    print()
    print(
        "Sending scheduled daily summary..."
    )

    try:
        result = (
            send_daily_summary_email()
        )

    except Exception as error:
        print(
            f"Daily summary failed: {error}"
        )

        # Do not update the last-send timestamp.
        # A later scheduled check can retry.
        return False

    sent_at = datetime.now(
        timezone.utc
    )

    set_last_daily_summary(
        sent_at
    )

    print(
        "Daily summary sent successfully."
    )

    print(
        "Recipient: "
        f"{result['recipient']}"
    )

    print(
        "Subject: "
        f"{result['subject']}"
    )

    if result.get(
        "email_id"
    ):
        print(
            "Resend ID: "
            f"{result['email_id']}"
        )

    return True


def run():
    send_summary_if_due()


def main():
    with capture_output():
        run()


if __name__ == "__main__":
    main()