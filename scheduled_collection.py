from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app_logging import (
    capture_output,
)

from browser_fetch import (
    close_browser_session,
)

from collection_lock import (
    CollectionAlreadyRunning,
    collection_lock,
)

from database_backup import (
    backup_database,
)

from collector import (
    reset_ao3_transport_state,
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
    get_collection_retry_after,
    set_collection_retry_after,
    clear_collection_retry_after,
)


FAILURE_RETRY_MINUTES = 60


def parse_timestamp(value):
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        timestamp = value

    else:
        timestamp = (
            datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

    if timestamp.tzinfo is None:
        timestamp = (
            timestamp.replace(
                tzinfo=timezone.utc
            )
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

    last_collection = (
        parse_timestamp(
            last_collection
        )
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
        reset_ao3_transport_state()

        collection_result = None
        discovery_result = None

        try:
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
                print(
                    "Collection encountered "
                    "an unexpected error: "
                    f"{error}"
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
                print(
                    "Work discovery encountered "
                    "an unexpected error: "
                    f"{error}"
                )
                print()

        finally:
            close_browser_session()

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

        now = datetime.now(
            timezone.utc
        )

        total_failure = False

        if collection_result is None:
            total_failure = True

        else:
            saved = (
                collection_result.get(
                    "saved",
                    0,
                )
            )

            failed = (
                collection_result.get(
                    "failed",
                    0,
                )
            )

            total_failure = (
                saved == 0
                and failed > 0
            )

        retry_after = None

        if total_failure:
            retry_after = (
                now
                + timedelta(
                    minutes=(
                        FAILURE_RETRY_MINUTES
                    )
                )
            )

            set_collection_retry_after(
                retry_after
            )

            print(
                "No snapshots were saved."
            )

            print(
                "Normal collection interval "
                "was not reset."
            )

            print(
                "Automatic retry will become "
                "eligible at "
                f"{retry_after.isoformat()}."
            )

        else:
            clear_collection_retry_after()

            set_last_scheduled_collection(
                now
            )

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

            "retry_after":
                (
                    retry_after.isoformat()
                    if retry_after
                    else None
                ),
        }
    

def run():
    initialize_database()

    interval_hours = (
        get_collection_interval()
    )

    now = datetime.now(
        timezone.utc
    )

    retry_after = (
        get_collection_retry_after()
    )

    retry_due = False

    if retry_after is not None:
        retry_after = (
            parse_timestamp(
                retry_after
            )
        )

        if now < retry_after:
            remaining = (
                retry_after - now
            )

            remaining_minutes = max(
                1,
                int(
                    remaining.total_seconds()
                    / 60
                ),
            )

            print(
                "Collection is in failure "
                "cooldown."
            )

            print(
                "Approximately "
                f"{remaining_minutes} minutes "
                "until the next retry."
            )

            return

        retry_due = True

        print(
            "Failure retry cooldown "
            "has expired."
        )

        print(
            "Retrying AO3 collection."
        )
        print()

    if not retry_due:
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
                f"{interval_hours}-hour "
                "interval."
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