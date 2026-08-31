from datetime import datetime, timezone

from database import (
    initialize_database,
    add_work,
    get_all_works,
    update_work,
    save_snapshot,
    get_snapshots_for_work,
    get_collection_interval,
    set_collection_interval,
)

from collection import collect_all_stats
from csv_importer import import_historical_csv


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
        print("9. Exit")
        print()

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
            print("Goodbye.")
            break

        else:
            print("Invalid option.")
            print()


if __name__ == "__main__":
    main()