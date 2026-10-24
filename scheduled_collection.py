from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app_logging import (
    capture_output,
)

from collection_lock import (
    CollectionAlreadyRunning,
    collection_lock,
)

from database_backup import (
    backup_database,
)

from collection import collect_all_stats

from discovery import (
    discover_and_add_new_works,
)

from database import (
    initialize_database,
    get_collection_interval,
    get_last_scheduled_collection,
    set_last_scheduled_collection,
)


def parse_timestamp(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        timestamp = value

    else:
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


def get_next_collection_time():
    interval_hours = (
        get_collection_interval()
    )

    last_collection = (
        get_last_scheduled_collection()
    )

    if last_collection is None:
        return None

    last_collection = parse_timestamp(
        last_collection
    )

    return (
        last_collection
        + timedelta(
            hours=interval_hours
        )
    )


def run_collection_cycle(
    trigger="scheduled",
):
    with collection_lock():
        print(
            f"Running {trigger} AO3 cycle..."
        )
        print()

        print(
            "Step 1: Collecting tracked works"
        )
        print()

        try:
            collection_result = (
                collect_all_stats()
            )

        except Exception as error:
            collection_result = None

            print(
                "Collection encountered "
                f"an unexpected error: {error}"
            )
            print()

        print(
            "Step 2: Checking for new works"
        )
        print()

        try:
            discovery_result = (
                discover_and_add_new_works()
            )

        except Exception as error:
            discovery_result = None

            print(
                "Work discovery encountered "
                f"an unexpected error: {error}"
            )
            print()

        print(
            f"{trigger.capitalize()} "
            "AO3 cycle complete."
        )
        print()

        print(
            "Checking daily database backup..."
        )

        backup_result = None

        try:
            backup_result = (
                backup_database()
            )

        except Exception as error:
            print(
                "Database backup failed: "
                f"{error}"
            )

        set_last_scheduled_collection()

        print(
            "Collection timestamp updated."
        )

        return {
            "collection":
                collection_result,

            "discovery":
                discovery_result,

            "backup":
                backup_result,
        }


def run():
    initialize_database()

    interval_hours = (
        get_collection_interval()
    )

    now = datetime.now(
        timezone.utc
    )

    next_collection = (
        get_next_collection_time()
    )

    if (
        next_collection is not None
        and now < next_collection
    ):
        remaining = (
            next_collection - now
        )

        remaining_minutes = max(
            1,
            int(
                remaining.total_seconds()
                / 60
            ),
        )

        print(
            "Scheduled collection is "
            "not due yet."
        )

        print(
            f"Approximately "
            f"{remaining_minutes} minutes "
            f"remaining in the "
            f"{interval_hours}-hour interval."
        )

        return

    print(
        "Scheduled collection is due."
    )
    print()

    try:
        run_collection_cycle(
            trigger="scheduled"
        )

    except CollectionAlreadyRunning:
        print(
            "Scheduled collection skipped "
            "because another collection is "
            "already in progress."
        )


def main():
    with capture_output():
        run()


if __name__ == "__main__":
    main()