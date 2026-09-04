from datetime import datetime, timezone

from email_summary import (
    send_daily_summary_email,
)

from database import (
    initialize_database,
    add_work,
    get_all_works,
    update_work,
    save_snapshot,
    get_snapshots_for_work,
    get_collection_interval,
    set_collection_interval,
    find_redundant_snapshots,
    delete_snapshots,
    get_null_stat_counts,
    replace_null_stats_with_zero,
    add_event,
    get_events_for_work,
    update_event,
    delete_event,
    event_type_exists,
    chapter_event_exists,
    get_daily_summary_recipient,
    set_daily_summary_recipient,
    get_daily_summary_time,
    set_daily_summary_time,
    get_daily_summary_sender,
    set_daily_summary_sender,
)

from collection import collect_all_stats
from csv_importer import import_historical_csv
from collector import (
    fetch_work_stats,
    fetch_chapter_metadata,
)

def list_works():
    works = get_all_works()

    print(f"Tracking {len(works)} works:")
    print()

    for work_id, ao3_work_id, title, url in works:
        print(f"{work_id}. {title}")
        print(f"   Work ID: {ao3_work_id}")
        print(f"   {url}")
        print()

    return works


def display_value(value):
    if value is None:
        return "—"

    return value


def select_work(prompt):
    works = list_works()

    work_id = input(prompt).strip()

    for work in works:
        if str(work[0]) == work_id:
            return work

    print("Work not found.")
    print()

    return None


def view_snapshots():
    selected_work = select_work(
        "Enter the number of the work to view: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    snapshots = get_snapshots_for_work(work_id)

    print()
    print(f'Snapshots for "{title}":')
    print()

    if not snapshots:
        print("No snapshots recorded yet.")
        print()
        return

    for snapshot in snapshots:
        (
            collected_at,
            hits,
            kudos,
            comments,
            public_bookmarks,
            word_count,
            chapters_published,
            chapters_total,
            subscriptions,
            total_bookmarks,
            comment_threads,
            source,
        ) = snapshot

        print(f"Collected: {collected_at}")
        print(f"  Hits: {display_value(hits)}")
        print(f"  Kudos: {display_value(kudos)}")
        print(f"  Comments: {display_value(comments)}")
        print(
            f"  Public bookmarks: "
            f"{display_value(public_bookmarks)}"
        )
        print(f"  Words: {display_value(word_count)}")
        print(
            f"  Chapters: "
            f"{display_value(chapters_published)}/"
            f"{display_value(chapters_total)}"
        )
        print(
            f"  Subscriptions: "
            f"{display_value(subscriptions)}"
        )
        print(
            f"  Total bookmarks: "
            f"{display_value(total_bookmarks)}"
        )
        print(
            f"  Comment threads: "
            f"{display_value(comment_threads)}"
        )
        print(f"  Source: {source}")
        print()


def get_manual_integer(prompt):
    while True:
        value = input(prompt).strip()

        if not value:
            return None

        try:
            number = int(value)

            if number < 0:
                print(
                    "Please enter 0 or "
                    "a positive number."
                )
                continue

            return number

        except ValueError:
            print("Please enter a whole number.")


def enter_manual_stats():
    selected_work = select_work(
        "Enter the number of the work to update: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    print()
    print(f'Manual snapshot for "{title}"')
    print("Leave any unavailable statistic blank.")
    print()

    while True:
        timestamp_value = input(
            "Snapshot date/time "
            "(YYYY-MM-DD HH:MM, "
            "or press Enter for now): "
        ).strip()

        if not timestamp_value:
            collected_at = datetime.now(
                timezone.utc
            )
            break

        try:
            entered_time = datetime.fromisoformat(
                timestamp_value
            )

            if entered_time.tzinfo is None:
                local_timezone = (
                    datetime.now()
                    .astimezone()
                    .tzinfo
                )

                entered_time = entered_time.replace(
                    tzinfo=local_timezone
                )

            collected_at = entered_time.astimezone(
                timezone.utc
            )

            break

        except ValueError:
            print(
                "Please use a date and time such as "
                "2026-08-30 21:15."
            )

    print()

    stats = {
        "hits": get_manual_integer("Hits: "),
        "kudos": get_manual_integer("Kudos: "),
        "comments": get_manual_integer(
            "Comments: "
        ),
        "public_bookmarks": get_manual_integer(
            "Public bookmarks: "
        ),
        "word_count": get_manual_integer(
            "Word count: "
        ),
        "chapters_published": get_manual_integer(
            "Chapters published: "
        ),
        "chapters_total": get_manual_integer(
            "Total chapters: "
        ),
        "subscriptions": get_manual_integer(
            "Subscriptions: "
        ),
        "total_bookmarks": get_manual_integer(
            "Total bookmarks: "
        ),
        "comment_threads": get_manual_integer(
            "Comment threads: "
        ),
    }

    save_snapshot(
        work_id,
        stats,
        source="manual",
        collected_at=collected_at,
    )

    print()
    print("Manual snapshot saved.")
    print()


def import_csv_data():
    print("Import historical AO3 snapshots from CSV.")
    print()

    file_path = input(
        "CSV file path: "
    ).strip()

    file_path = file_path.strip('"')

    if not file_path:
        print("Import cancelled.")
        print()
        return

    try:
        result = import_historical_csv(
            file_path
        )

    except Exception as error:
        print()
        print(f"Import failed: {error}")
        print()
        return

    print()
    print("Import complete.")
    print(f"  Snapshots added: {result['added']}")
    print(
        f"  Duplicates skipped: "
        f"{result['duplicates']}"
    )
    print(f"  Errors: {result['errors']}")

    if result["error_messages"]:
        print()
        print("Rows with errors:")

        for message in result["error_messages"]:
            print(f"  {message}")

    print()


def configure_collection_interval():
    current_interval = get_collection_interval()

    print(
        f"Current automatic collection interval: "
        f"{current_interval:g} hours"
    )
    print()

    new_value = input(
        "Enter a new interval in hours "
        "(or press Enter to keep the current value): "
    ).strip()

    if not new_value:
        print("Collection interval unchanged.")
        print()
        return

    try:
        hours = float(new_value)
    except ValueError:
        print("Please enter a number.")
        print()
        return

    if hours <= 0:
        print(
            "Collection interval must be "
            "greater than 0."
        )
        print()
        return

    set_collection_interval(hours)

    print(
        f"Collection interval set to "
        f"{hours:g} hours."
    )
    print()


def cleanup_database():
    redundant = find_redundant_snapshots()

    print("Database cleanup")
    print()

    if not redundant:
        print("No redundant snapshots found.")
        print()
        return

    print(
        f"Found {len(redundant)} redundant "
        f"snapshot(s)."
    )
    print()

    current_title = None

    for item in redundant:
        if item["title"] != current_title:
            current_title = item["title"]

            print(current_title)

        print(
            f"  KEEP:   "
            f"{item['keep_collected_at']} "
            f"[{item['keep_source']}]"
        )

        print(
            f"  REMOVE: "
            f"{item['remove_collected_at']} "
            f"[{item['remove_source']}]"
        )

        print()

    print(
        "Only snapshots whose statistics are "
        "identical to the previous snapshot "
        "will be removed."
    )

    print(
        "The earliest snapshot in each "
        "unchanged run will be kept."
    )

    print()

    confirmation = input(
        "Type DELETE to remove these snapshots, "
        "or press Enter to cancel: "
    ).strip()

    if confirmation != "DELETE":
        print()
        print("Cleanup cancelled.")
        print()
        return

    snapshot_ids = [
        item["snapshot_id"]
        for item in redundant
    ]

    deleted_count = delete_snapshots(
        snapshot_ids
    )

    print()
    print(
        f"Cleanup complete. "
        f"Deleted {deleted_count} "
        f"redundant snapshot(s)."
    )
    print()


def normalize_null_stats():
    from database import (
        get_null_stat_counts,
        replace_null_stats_with_zero,
    )

    counts = get_null_stat_counts()

    total_nulls = sum(counts.values())

    print("NULL value cleanup")
    print()

    if total_nulls == 0:
        print("No NULL statistic values found.")
        print()
        return

    print(
        f"Found {total_nulls} NULL statistic "
        f"value(s):"
    )
    print()

    labels = {
        "hits": "Hits",
        "kudos": "Kudos",
        "comments": "Comments",
        "public_bookmarks": "Public bookmarks",
        "word_count": "Word count",
        "chapters_published": "Chapters published",
        "chapters_total": "Total chapters",
        "subscriptions": "Subscriptions",
        "total_bookmarks": "Total bookmarks",
        "comment_threads": "Comment threads",
    }

    for field, label in labels.items():
        count = counts[field]

        if count:
            print(f"  {label}: {count}")

    print()
    print(
        "Every NULL statistic listed above "
        "will be changed to 0."
    )
    print(
        "This cannot distinguish between "
        "\"unknown\" and a true zero afterward."
    )
    print()

    confirmation = input(
        "Type ZERO to make these changes, "
        "or press Enter to cancel: "
    ).strip()

    if confirmation != "ZERO":
        print()
        print("NULL cleanup cancelled.")
        print()
        return

    result = replace_null_stats_with_zero()

    print()
    print("NULL cleanup complete.")
    print(
        f"  Snapshots updated: "
        f"{result['rows_updated']}"
    )
    print(
        f"  NULL values changed to 0: "
        f"{result['values_replaced']}"
    )
    print()


def add_work_event():
    selected_work = select_work(
        "Enter the number of the work: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    print()
    print(f'Add event for "{title}"')
    print()
    print("1. Work published")
    print("2. Chapter published")
    print("3. Work completed")
    print("4. Note")
    print()

    event_choice = input(
        "Event type: "
    ).strip()

    event_types = {
        "1": "work_published",
        "2": "chapter_published",
        "3": "work_completed",
        "4": "note",
    }

    if event_choice not in event_types:
        print("Invalid event type.")
        print()
        return

    event_type = event_types[event_choice]

    while True:
        timestamp_value = input(
            "Event date/time "
            "(YYYY-MM-DD HH:MM): "
        ).strip()

        try:
            occurred_at = datetime.fromisoformat(
                timestamp_value
            )

            if occurred_at.tzinfo is None:
                local_timezone = (
                    datetime.now()
                    .astimezone()
                    .tzinfo
                )

                occurred_at = occurred_at.replace(
                    tzinfo=local_timezone
                )

            occurred_at = occurred_at.astimezone(
                timezone.utc
            )

            break

        except ValueError:
            print(
                "Please use a date and time such as "
                "2026-08-30 21:15."
            )

    chapter_number = None

    if event_type == "chapter_published":
        while True:
            chapter_value = input(
                "Chapter number: "
            ).strip()

            try:
                chapter_number = int(
                    chapter_value
                )

                if chapter_number <= 0:
                    raise ValueError

                break

            except ValueError:
                print(
                    "Please enter a positive "
                    "whole number."
                )

    description = input(
        "Description "
        "(optional, press Enter to skip): "
    ).strip()

    if not description:
        description = None

    add_event(
        work_id,
        occurred_at,
        event_type,
        chapter_number,
        description,
    )

    print()
    print("Event saved.")
    print()


def view_work_events():
    selected_work = select_work(
        "Enter the number of the work: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    events = get_events_for_work(
        work_id
    )

    print()
    print(f'Events for "{title}":')
    print()

    if not events:
        print("No events recorded.")
        print()
        return

    labels = {
        "work_published": "Work published",
        "chapter_published": "Chapter published",
        "work_completed": "Work completed",
        "note": "Note",
    }

    for (
        event_id,
        occurred_at,
        event_type,
        chapter_number,
        description,
    ) in events:

        print(
            f"{event_id}. "
            f"{labels.get(event_type, event_type)}"
        )

        print(
            f"   Date: {occurred_at}"
        )

        if chapter_number is not None:
            print(
                f"   Chapter: {chapter_number}"
            )

        if description:
            print(
                f"   {description}"
            )

        print()


def select_work_event(
    work_id,
    title,
    prompt,
):
    events = get_events_for_work(work_id)

    if not events:
        print()
        print(
            f'No events recorded for "{title}".'
        )
        print()
        return None

    labels = {
        "work_published": "Work published",
        "chapter_published": "Chapter published",
        "work_completed": "Work completed",
        "note": "Note",
    }

    print()
    print(f'Events for "{title}":')
    print()

    for index, event in enumerate(
        events,
        start=1,
    ):
        (
            event_id,
            occurred_at,
            event_type,
            chapter_number,
            description,
        ) = event

        label = labels.get(
            event_type,
            event_type,
        )

        if chapter_number is not None:
            label += (
                f" — Chapter {chapter_number}"
            )

        print(
            f"{index}. {label}"
        )
        print(
            f"   {occurred_at}"
        )

        if description:
            print(
                f"   {description}"
            )

    print()

    choice = input(prompt).strip()

    try:
        choice_number = int(choice)

    except ValueError:
        print("Invalid selection.")
        print()
        return None

    if not (
        1
        <= choice_number
        <= len(events)
    ):
        print("Invalid selection.")
        print()
        return None

    return events[choice_number - 1]


def edit_work_event():
    selected_work = select_work(
        "Enter the number of the work: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    selected_event = select_work_event(
        work_id,
        title,
        "Enter the number of the event "
        "to edit: ",
    )

    if selected_event is None:
        return

    (
        event_id,
        current_occurred_at,
        current_event_type,
        current_chapter_number,
        current_description,
    ) = selected_event

    event_labels = {
        "work_published": "Work published",
        "chapter_published": "Chapter published",
        "work_completed": "Work completed",
        "note": "Note",
    }

    print()
    print("Press Enter to keep a value.")
    print()

    print(
        "1. Work published"
    )
    print(
        "2. Chapter published"
    )
    print(
        "3. Work completed"
    )
    print(
        "4. Note"
    )
    print()

    event_types = {
        "1": "work_published",
        "2": "chapter_published",
        "3": "work_completed",
        "4": "note",
    }

    current_label = event_labels.get(
        current_event_type,
        current_event_type,
    )

    event_choice = input(
        f"Event type "
        f"[{current_label}]: "
    ).strip()

    if event_choice:
        if event_choice not in event_types:
            print("Invalid event type.")
            print()
            return

        new_event_type = event_types[
            event_choice
        ]

    else:
        new_event_type = (
            current_event_type
        )

    timestamp_value = input(
        f"Event date/time "
        f"[{current_occurred_at}]: "
    ).strip()

    if timestamp_value:
        try:
            new_occurred_at = (
                datetime.fromisoformat(
                    timestamp_value
                )
            )

            if new_occurred_at.tzinfo is None:
                local_timezone = (
                    datetime.now()
                    .astimezone()
                    .tzinfo
                )

                new_occurred_at = (
                    new_occurred_at.replace(
                        tzinfo=local_timezone
                    )
                )

            new_occurred_at = (
                new_occurred_at.astimezone(
                    timezone.utc
                )
            )

        except ValueError:
            print(
                "Invalid date/time. "
                "Use something like "
                "2026-08-30 21:15."
            )
            print()
            return

    else:
        new_occurred_at = (
            current_occurred_at
        )

    if (
        new_event_type
        == "chapter_published"
    ):
        current_chapter_display = (
            current_chapter_number
            if current_chapter_number
            is not None
            else ""
        )

        chapter_value = input(
            f"Chapter number "
            f"[{current_chapter_display}]: "
        ).strip()

        if chapter_value:
            try:
                new_chapter_number = int(
                    chapter_value
                )

                if new_chapter_number <= 0:
                    raise ValueError

            except ValueError:
                print(
                    "Chapter number must "
                    "be a positive whole number."
                )
                print()
                return

        else:
            new_chapter_number = (
                current_chapter_number
            )

        if new_chapter_number is None:
            print(
                "A chapter-published event "
                "needs a chapter number."
            )
            print()
            return

    else:
        new_chapter_number = None

    current_description_display = (
        current_description
        if current_description
        else ""
    )

    description_value = input(
        f"Description "
        f"[{current_description_display}] "
        "(Enter keeps it, CLEAR removes it): "
    ).strip()

    if (
        description_value.upper()
        == "CLEAR"
    ):
        new_description = None

    elif description_value:
        new_description = (
            description_value
        )

    else:
        new_description = (
            current_description
        )

    update_event(
        event_id,
        new_occurred_at,
        new_event_type,
        new_chapter_number,
        new_description,
    )

    print()
    print("Event updated.")
    print()


def delete_work_event():
    selected_work = select_work(
        "Enter the number of the work: "
    )

    if selected_work is None:
        return

    work_id, _, title, _ = selected_work

    selected_event = select_work_event(
        work_id,
        title,
        "Enter the number of the event "
        "to delete: ",
    )

    if selected_event is None:
        return

    (
        event_id,
        occurred_at,
        event_type,
        chapter_number,
        description,
    ) = selected_event

    labels = {
        "work_published": "Work published",
        "chapter_published": "Chapter published",
        "work_completed": "Work completed",
        "note": "Note",
    }

    print()
    print("Event to delete:")
    print(
        labels.get(
            event_type,
            event_type,
        )
    )
    print(
        f"Date: {occurred_at}"
    )

    if chapter_number is not None:
        print(
            f"Chapter: {chapter_number}"
        )

    if description:
        print(
            f"Description: {description}"
        )

    print()

    confirmation = input(
        "Type DELETE to permanently "
        "remove this event: "
    ).strip()

    if confirmation != "DELETE":
        print("Deletion cancelled.")
        print()
        return

    delete_event(event_id)

    print()
    print("Event deleted.")
    print()


def backfill_work_events():
    selected_work = select_work(
        "Enter the number of the work: "
    )

    if selected_work is None:
        return

    (
        work_id,
        ao3_work_id,
        title,
        url,
    ) = selected_work

    print()
    print(
        f'Backfilling AO3 events for "{title}"...'
    )
    print()

    try:
        stats = fetch_work_stats(url)

    except Exception as error:
        print(
            f"Could not retrieve AO3 work "
            f"metadata: {error}"
        )
        print()
        return

    try:
        chapters = fetch_chapter_metadata(
            url
        )

    except Exception as error:
        print(
            f"Could not retrieve AO3 chapter "
            f"metadata: {error}"
        )
        print()
        return

    created = 0
    skipped = 0

    published_date = stats.get(
        "published_date"
    )

    if published_date:
        if event_type_exists(
            work_id,
            "work_published",
        ):
            print(
                "Work publication event "
                "already exists; skipping."
            )

            skipped += 1

        else:
            add_event(
                work_id=work_id,
                occurred_at=published_date,
                event_type="work_published",
                description=(
                    "Historical publication date "
                    "retrieved from AO3."
                ),
                source="ao3_backfill",
                date_source="ao3_published",
                date_precision="date",
            )

            created += 1

            print(
                "Added work publication event: "
                f"{published_date}"
            )

    else:
        print(
            "AO3 publication date was not "
            "available; no publication event "
            "was created."
        )

    for chapter in chapters:
        chapter_number = chapter.get(
            "chapter_number"
        )

        if chapter_number is None:
            continue

        # Chapter 1 is represented by the
        # work-published event.
        if chapter_number == 1:
            continue

        if chapter_event_exists(
            work_id,
            chapter_number,
        ):
            print(
                f"Chapter {chapter_number} "
                "already has an event; skipping."
            )

            skipped += 1
            continue

        published_date = chapter.get(
            "published_date"
        )

        if not published_date:
            print(
                f"Chapter {chapter_number} "
                "has no readable AO3 date; "
                "skipping."
            )

            skipped += 1
            continue

        chapter_title = chapter.get(
            "title"
        )

        if chapter_title:
            description = (
                f"{chapter_title} — "
                "Historical publication date "
                "retrieved from AO3."
            )

        else:
            description = (
                "Historical publication date "
                "retrieved from AO3."
            )

        add_event(
            work_id=work_id,
            occurred_at=published_date,
            event_type="chapter_published",
            chapter_number=chapter_number,
            description=description,
            source="ao3_backfill",
            date_source="ao3_chapter_date",
            date_precision="date",
        )

        created += 1

        print(
            f"Added Chapter "
            f"{chapter_number}: "
            f"{published_date}"
        )

    print()
    print("Backfill complete.")
    print(
        f"  Events created: {created}"
    )
    print(
        f"  Existing/unavailable: {skipped}"
    )
    print()


def configure_daily_summary():
    current_recipient = (
        get_daily_summary_recipient()
    )

    current_sender = (
        get_daily_summary_sender()
    )

    current_time = (
        get_daily_summary_time()
    )

    print("Daily summary settings")
    print()

    print(
        "Current sender: "
        f"{current_sender or 'Not set'}"
    )

    print(
        "Current recipient: "
        f"{current_recipient or 'Not set'}"
    )

    print(
        "Current delivery time: "
        f"{current_time or 'Not set'}"
    )

    print()
    print(
        "Press Enter to keep the "
        "current value."
    )
    print()

    sender = input(
        "Sender email address: "
    ).strip()

    if sender:
        if (
            "@" not in sender
            or "." not in sender.split(
                "@",
                1,
            )[-1]
        ):
            print(
                "That does not look like "
                "a valid sender address."
            )
            print()
            return

        set_daily_summary_sender(
            sender
        )

    recipient = input(
        "Recipient email address: "
    ).strip()

    if recipient:
        if (
            "@" not in recipient
            or "." not in recipient.split(
                "@",
                1,
            )[-1]
        ):
            print(
                "That does not look like "
                "a valid email address."
            )
            print()
            return

        set_daily_summary_recipient(
            recipient
        )

    while True:
        summary_time = input(
            "Delivery time "
            "(24-hour HH:MM): "
        ).strip()

        if not summary_time:
            break

        try:
            parsed_time = (
                datetime.strptime(
                    summary_time,
                    "%H:%M",
                )
            )

            normalized_time = (
                parsed_time.strftime(
                    "%H:%M"
                )
            )

            set_daily_summary_time(
                normalized_time
            )

            break

        except ValueError:
            print(
                "Please enter the time "
                "as HH:MM, for example "
                "08:30 or 19:00."
            )

    print()
    print("Daily summary settings saved.")
    print()

    print(
        "Sender: "
        f"{get_daily_summary_sender() or 'Not set'}"
    )

    print(
        "Recipient: "
        f"{get_daily_summary_recipient() or 'Not set'}"
    )

    print(
        "Delivery time: "
        f"{get_daily_summary_time() or 'Not set'}"
    )

    print()


def send_test_daily_summary():
    print(
        "Sending daily summary..."
    )
    print()

    try:
        result = (
            send_daily_summary_email()
        )

    except Exception as error:
        print(
            f"Email failed: {error}"
        )
        print()

        return

    print(
        "Email sent successfully."
    )

    print(
        "Recipient: "
        f"{result['recipient']}"
    )

    print(
        "Subject: "
        f"{result['subject']}"
    )

    print()


def main():
    initialize_database()

    print("AO3 Stats Dashboard")
    print()

    while True:
        print("1. Add work")
        print("2. List works")
        print("3. Edit work")
        print("4. Fetch and save current stats")
        print("5. Enter manual snapshot")
        print("6. Import historical CSV")
        print("7. View snapshots")
        print("8. Collection interval")
        print("9. Database cleanup")
        print("10. Change NULL stats to 0"        )
        print("11. Add work event")
        print("12. View work events")
        print("13. Edit work event")
        print("14. Delete work event")
        print("15. Backfill AO3 events")
        print("16. Daily summary settings")
        print("17. Send test daily summary")
        print("18. Exit")

        choice = input(
            "Choose an option: "
        ).strip()

        print()

        if choice == "1":
            ao3_work_id = input(
                "AO3 work ID: "
            ).strip()

            title = input(
                "Title: "
            ).strip()

            add_work(
                ao3_work_id,
                title,
            )

            print(
                f'Added "{title}" '
                f"to the database."
            )
            print()

        elif choice == "2":
            list_works()

        elif choice == "3":
            selected_work = select_work(
                "Enter the number of the "
                "work to edit: "
            )

            if selected_work is None:
                continue

            (
                work_id,
                current_ao3_work_id,
                current_title,
                _,
            ) = selected_work

            print(
                "Press Enter to keep "
                "the current value."
            )
            print()

            new_ao3_work_id = input(
                f"AO3 work ID "
                f"[{current_ao3_work_id}]: "
            ).strip()

            new_title = input(
                f"Title [{current_title}]: "
            ).strip()

            if not new_ao3_work_id:
                new_ao3_work_id = (
                    current_ao3_work_id
                )

            if not new_title:
                new_title = current_title

            update_work(
                work_id,
                new_ao3_work_id,
                new_title,
            )

            print(
                f'Updated "{new_title}".'
            )
            print()

        elif choice == "4":
            collect_all_stats()

        elif choice == "5":
            enter_manual_stats()

        elif choice == "6":
            import_csv_data()

        elif choice == "7":
            view_snapshots()

        elif choice == "8":
            configure_collection_interval()

        elif choice == "9":
            cleanup_database()

        elif choice == "10":
            normalize_null_stats()

        elif choice == "11":
            add_work_event()

        elif choice == "12":
            view_work_events()

        elif choice == "13":
            edit_work_event()

        elif choice == "14":
            delete_work_event()

        elif choice == "15":
            backfill_work_events()

        elif choice == "16":
            configure_daily_summary()

        elif choice == "17":
            send_test_daily_summary()

        elif choice == "18":
            print("Goodbye.")
            break

        else:
            print("Invalid option.")
            print()


if __name__ == "__main__":
    main()