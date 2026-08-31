from datetime import datetime, timedelta, timezone

from collection import collect_all_stats
from database import (
    initialize_database,
    get_collection_interval,
    get_last_scheduled_collection,
    set_last_scheduled_collection,
)


def get_next_collection_time():
    interval_hours = get_collection_interval()
    last_collection = get_last_scheduled_collection()

    if last_collection is None:
        return None

    return last_collection + timedelta(hours=interval_hours)


def main():
    initialize_database()

    interval_hours = get_collection_interval()
    next_collection = get_next_collection_time()
    now = datetime.now(timezone.utc)

    if next_collection is not None and now < next_collection:
        remaining = next_collection - now
        remaining_minutes = max(
            1,
            int(remaining.total_seconds() / 60),
        )

        print(
            f"Collection is not due yet. "
            f"Approximately {remaining_minutes} minutes remaining."
        )
        return

    print(
        f"Scheduled collection due "
        f"(interval: {interval_hours:g} hours)."
    )
    print()

    collect_all_stats()

    set_last_scheduled_collection()

    print("Scheduled collection timestamp updated.")


if __name__ == "__main__":
    main()