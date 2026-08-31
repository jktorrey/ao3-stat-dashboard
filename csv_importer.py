import csv
from datetime import datetime, timezone
from pathlib import Path

from database import (
    get_work_by_ao3_id,
    save_snapshot,
    snapshot_exists,
)


STAT_FIELDS = [
    "hits",
    "kudos",
    "comments",
    "public_bookmarks",
    "word_count",
    "chapters_published",
    "chapters_total",
    "subscriptions",
    "total_bookmarks",
    "comment_threads",
]


def parse_optional_integer(value, field_name):
    if value is None:
        return None

    value = value.strip()

    if not value or value in {"—", "-"}:
        return None

    value = value.replace(",", "")

    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(
            f"{field_name} must be a whole number"
        ) from error

    if number < 0:
        raise ValueError(
            f"{field_name} cannot be negative"
        )

    return number


def parse_timestamp(value):
    value = value.strip()

    if not value:
        raise ValueError("collected_at is required")

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            "collected_at must look like "
            "2026-08-23 19:42 "
            "or 2026-08-23 19:42-04:00"
        ) from error

    if timestamp.tzinfo is None:
        local_timezone = (
            datetime.now()
            .astimezone()
            .tzinfo
        )

        timestamp = timestamp.replace(
            tzinfo=local_timezone
        )

    return timestamp.astimezone(timezone.utc)


def import_historical_csv(file_path):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    added_count = 0
    duplicate_count = 0
    error_count = 0
    errors = []

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            raise ValueError(
                "CSV file does not contain a header row."
            )

        required_columns = {
            "ao3_work_id",
            "collected_at",
        }

        missing_columns = (
            required_columns
            - set(reader.fieldnames)
        )

        if missing_columns:
            missing = ", ".join(
                sorted(missing_columns)
            )

            raise ValueError(
                f"CSV is missing required columns: "
                f"{missing}"
            )

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            try:
                ao3_work_id = (
                    row.get("ao3_work_id", "")
                    .strip()
                )

                if not ao3_work_id:
                    raise ValueError(
                        "ao3_work_id is required"
                    )

                try:
                    ao3_work_id = int(ao3_work_id)
                except ValueError as error:
                    raise ValueError(
                        "ao3_work_id must be a number"
                    ) from error

                work = get_work_by_ao3_id(
                    ao3_work_id
                )

                if work is None:
                    raise ValueError(
                        f"AO3 work ID {ao3_work_id} "
                        f"is not in the database"
                    )

                work_id = work[0]

                collected_at = parse_timestamp(
                    row.get("collected_at", "")
                )

                if snapshot_exists(
                    work_id,
                    collected_at,
                ):
                    duplicate_count += 1
                    continue

                stats = {}

                for field in STAT_FIELDS:
                    stats[field] = (
                        parse_optional_integer(
                            row.get(field),
                            field,
                        )
                    )

                if all(
                    value is None
                    for value in stats.values()
                ):
                    raise ValueError(
                        "row contains no statistics"
                    )

                save_snapshot(
                    work_id,
                    stats,
                    source="csv_import",
                    collected_at=collected_at,
                )

                added_count += 1

            except Exception as error:
                error_count += 1

                errors.append(
                    f"Row {row_number}: {error}"
                )

    return {
        "added": added_count,
        "duplicates": duplicate_count,
        "errors": error_count,
        "error_messages": errors,
    }