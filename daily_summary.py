import sqlite3
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pandas as pd
from tzlocal import get_localzone

from dashboard_data import (
    get_period_changes,
)

from database import (
    DATABASE_NAME,
    initialize_database,
)


SUMMARY_HOURS = 24

LOCAL_TIMEZONE = get_localzone()


EVENT_LABELS = {
    "work_published": "Work published",
    "chapter_published": "Chapter published",
    "work_completed": "Work completed",
    "note": "Note",
}


def format_change(value):
    if value is None:
        return "—"

    if pd.isna(value):
        return "—"

    value = int(value)

    if value > 0:
        return f"+{value:,}"

    return f"{value:,}"


def format_local_datetime(value):
    if value is None:
        return "—"

    timestamp = pd.to_datetime(
        value,
        format="mixed",
        utc=True,
    )

    local_timestamp = timestamp.tz_convert(
        LOCAL_TIMEZONE
    )

    return local_timestamp.strftime(
        "%b %d, %Y %I:%M %p %Z"
    )


def get_recent_events(hours=24):
    connection = sqlite3.connect(
        DATABASE_NAME
    )

    events = pd.read_sql_query(
        """
        SELECT
            events.id,
            works.title,
            events.occurred_at,
            events.event_type,
            events.chapter_number,
            events.description,
            events.source,
            events.date_source,
            events.date_precision,
            events.detected_at
        FROM events
        JOIN works
            ON works.id = events.work_id
        ORDER BY events.occurred_at, events.id
        """,
        connection,
    )

    connection.close()

    if events.empty:
        return events

    now_utc = datetime.now(
        timezone.utc
    )

    cutoff_utc = (
        now_utc
        - timedelta(hours=hours)
    )

    now_local = now_utc.astimezone(
        LOCAL_TIMEZONE
    )

    cutoff_local = cutoff_utc.astimezone(
        LOCAL_TIMEZONE
    )

    recent_rows = []

    for _, event in events.iterrows():
        precision = event[
            "date_precision"
        ]

        occurred_at = event[
            "occurred_at"
        ]

        if precision == "date":
            event_date = pd.to_datetime(
                occurred_at,
                format="mixed",
            ).date()

            # AO3 supplied only a calendar date,
            # so we cannot make an exact 24-hour
            # comparison. Include dates that
            # overlap the local summary window.
            if (
                cutoff_local.date()
                <= event_date
                <= now_local.date()
            ):
                recent_rows.append(
                    event
                )

        else:
            event_time = pd.to_datetime(
                occurred_at,
                format="mixed",
                utc=True,
            )

            if (
                cutoff_utc
                <= event_time.to_pydatetime()
                <= now_utc
            ):
                recent_rows.append(
                    event
                )

    if not recent_rows:
        return events.iloc[0:0].copy()

    return pd.DataFrame(
        recent_rows
    )


def format_event(event):
    event_type = event[
        "event_type"
    ]

    title = event["title"]

    label = EVENT_LABELS.get(
        event_type,
        event_type,
    )

    if (
        event_type
        == "chapter_published"
        and pd.notna(
            event["chapter_number"]
        )
    ):
        chapter_number = int(
            event["chapter_number"]
        )

        label = (
            f"Chapter {chapter_number} "
            f"published"
        )

    if (
        event["date_precision"]
        == "date"
    ):
        event_date = pd.to_datetime(
            event["occurred_at"],
            format="mixed",
        )

        date_text = (
            event_date.strftime(
                "%b %d, %Y"
            )
        )

        date_text += " (date only)"

    else:
        date_text = (
            format_local_datetime(
                event["occurred_at"]
            )
        )

    return (
        f"{title}: {label} — "
        f"{date_text}"
    )


def build_daily_summary(
    hours=SUMMARY_HOURS,
):
    initialize_database()

    changes = get_period_changes(
        hours
    )

    recent_events = get_recent_events(
        hours
    )

    now_local = datetime.now(
        timezone.utc
    ).astimezone(
        LOCAL_TIMEZONE
    )

    lines = []

    lines.append(
        "AO3 Daily Stats Summary"
    )

    lines.append(
        now_local.strftime(
            "%B %d, %Y"
        )
    )

    lines.append("")

    lines.append(
        f"Previous {hours} hours"
    )

    lines.append("")

    if changes.empty:
        lines.append(
            "No tracked works were found."
        )

        return "\n".join(lines)

    total_works = len(changes)

    available = (
        changes[
            "baseline_collected_at"
        ]
        .notna()
        .sum()
    )

    full_coverage = (
        total_works > 0
        and available == total_works
    )

    lines.append("Overall")

    if full_coverage:
        hits_change = int(
            changes[
                "hits_change"
            ].sum()
        )

        kudos_change = int(
            changes[
                "kudos_change"
            ].sum()
        )

        comments_change = int(
            changes[
                "comments_change"
            ].sum()
        )

        bookmarks_change = int(
            changes[
                "bookmarks_change"
            ].sum()
        )

        lines.append(
            "  Hits gained: "
            f"{format_change(hits_change)}"
        )

        lines.append(
            "  Kudos gained: "
            f"{format_change(kudos_change)}"
        )

        lines.append(
            "  Comments gained: "
            f"{format_change(comments_change)}"
        )

        lines.append(
            "  Bookmarks gained: "
            f"{format_change(bookmarks_change)}"
        )

    else:
        lines.append(
            "  Portfolio totals unavailable."
        )

        lines.append(
            f"  24-hour baseline coverage: "
            f"{available} of "
            f"{total_works} works."
        )

    lines.append("")

    lines.append("By work")

    work_changes = changes.sort_values(
        by="title"
    )

    for _, work in (
        work_changes.iterrows()
    ):
        title = work["title"]

        lines.append("")
        lines.append(title)

        if pd.isna(
            work[
                "baseline_collected_at"
            ]
        ):
            lines.append(
                "  No 24-hour baseline yet."
            )

            continue

        lines.append(
            "  Hits: "
            f"{format_change(work['hits_change'])}"
        )

        lines.append(
            "  Kudos: "
            f"{format_change(work['kudos_change'])}"
        )

        lines.append(
            "  Comments: "
            f"{format_change(work['comments_change'])}"
        )

        lines.append(
            "  Bookmarks: "
            f"{format_change(work['bookmarks_change'])}"
        )

        baseline_hours = work[
            "baseline_hours"
        ]

        if pd.notna(
            baseline_hours
        ):
            lines.append(
                "  Actual comparison window: "
                f"{float(baseline_hours):.1f} hours"
            )

    lines.append("")
    lines.append("Recent activity")

    if recent_events.empty:
        lines.append(
            "  No publication events "
            "in this period."
        )

    else:
        for _, event in (
            recent_events.iterrows()
        ):
            lines.append(
                "  "
                + format_event(event)
            )

    return "\n".join(lines)


def main():
    summary = build_daily_summary()

    print()
    print(summary)
    print()


if __name__ == "__main__":
    main()