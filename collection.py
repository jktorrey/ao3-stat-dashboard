from datetime import datetime, timezone

from collector import (
    fetch_work_stats,
    fetch_chapter_metadata,
)

from database import (
    initialize_database,
    get_all_works,
    save_snapshot,
    add_event,
    get_latest_public_chapter_count,
    chapter_event_exists,
)


def create_detected_chapter_events(
    work_id,
    title,
    url,
    previous_chapter_count,
    current_chapter_count,
    detected_at,
):
    if previous_chapter_count is None:
        return 0

    if current_chapter_count is None:
        return 0

    if (
        current_chapter_count
        <= previous_chapter_count
    ):
        return 0

    print(
        f"  Chapter count increased: "
        f"{previous_chapter_count} -> "
        f"{current_chapter_count}"
    )

    chapter_metadata = []

    try:
        chapter_metadata = (
            fetch_chapter_metadata(url)
        )

    except Exception as error:
        print(
            "  Could not retrieve AO3 chapter "
            f"dates: {error}"
        )

        print(
            "  Falling back to collection "
            "timestamp for new chapter events."
        )

    metadata_by_number = {
        chapter["chapter_number"]: chapter
        for chapter in chapter_metadata
    }

    events_created = 0

    for chapter_number in range(
        previous_chapter_count + 1,
        current_chapter_count + 1,
    ):
        if chapter_event_exists(
            work_id,
            chapter_number,
        ):
            print(
                f"  Chapter {chapter_number} "
                "already has an event; skipping."
            )
            continue

        chapter = metadata_by_number.get(
            chapter_number
        )

        if (
            chapter is not None
            and chapter.get(
                "published_date"
            )
        ):
            occurred_at = chapter[
                "published_date"
            ]

            date_source = (
                "ao3_chapter_date"
            )

            date_precision = "date"

        else:
            occurred_at = detected_at

            date_source = (
                "collector_detected"
            )

            date_precision = "datetime"

        description_parts = []

        if chapter is not None:
            chapter_title = chapter.get(
                "title"
            )

            if chapter_title:
                description_parts.append(
                    chapter_title
                )

        description_parts.append(
            "Automatically detected when "
            "AO3 chapter count changed "
            f"from {previous_chapter_count} "
            f"to {current_chapter_count}."
        )

        description = " — ".join(
            description_parts
        )

        add_event(
            work_id=work_id,
            occurred_at=occurred_at,
            event_type="chapter_published",
            chapter_number=chapter_number,
            description=description,
            source="ao3_detected",
            date_source=date_source,
            date_precision=date_precision,
            detected_at=detected_at,
        )

        events_created += 1

        if date_precision == "date":
            print(
                f"  Added Chapter "
                f"{chapter_number} event "
                f"using AO3 date "
                f"{occurred_at}."
            )

        else:
            print(
                f"  Added Chapter "
                f"{chapter_number} event "
                "using collection timestamp."
            )

    return events_created


def collect_all_stats():
    initialize_database()

    works = get_all_works()

    if not works:
        print("No works are being tracked.")
        print()

        return {
            "saved": 0,
            "failed": 0,
            "events_created": 0,
        }

    saved = 0
    failed = 0
    events_created = 0

    for (
        work_id,
        ao3_work_id,
        title,
        url,
    ) in works:
        print(f'Collecting "{title}"...')

        previous_chapter_count = (
            get_latest_public_chapter_count(
                work_id
            )
        )

        try:
            stats = fetch_work_stats(
                url
            )

        except Exception as error:
            failed += 1

            print(
                f"  Collection failed: {error}"
            )
            print()

            continue

        detected_at = datetime.now(
            timezone.utc
        )

        print(
            f"  Hits: {stats.get('hits')}"
        )
        print(
            f"  Kudos: {stats.get('kudos')}"
        )
        print(
            f"  Comments: "
            f"{stats.get('comments')}"
        )
        print(
            f"  Public bookmarks: "
            f"{stats.get('public_bookmarks')}"
        )
        print(
            f"  Words: "
            f"{stats.get('word_count')}"
        )
        print(
            "  Chapters: "
            f"{stats.get('chapters_published')}"
            "/"
            f"{stats.get('chapters_total')}"
        )

        save_snapshot(
            work_id,
            stats,
            source="ao3_public",
            collected_at=detected_at,
        )

        saved += 1

        try:
            new_events = (
                create_detected_chapter_events(
                    work_id=work_id,
                    title=title,
                    url=url,
                    previous_chapter_count=(
                        previous_chapter_count
                    ),
                    current_chapter_count=(
                        stats.get(
                            "chapters_published"
                        )
                    ),
                    detected_at=detected_at,
                )
            )

            events_created += new_events

        except Exception as error:
            print(
                "  Snapshot saved, but chapter "
                f"event detection failed: {error}"
            )

        print()

    print("Collection complete.")
    print(
        f"  Snapshots saved: {saved}"
    )
    print(
        f"  Failed: {failed}"
    )
    print(
        f"  Chapter events created: "
        f"{events_created}"
    )
    print()

    return {
        "saved": saved,
        "failed": failed,
        "events_created": events_created,
    }


def main():
    collect_all_stats()


if __name__ == "__main__":
    main()