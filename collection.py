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
    get_latest_public_chapter_state,
    chapter_event_exists,
    event_type_exists,
)


def is_complete(
    chapters_published,
    chapters_total,
):
    return (
        chapters_published is not None
        and chapters_total is not None
        and chapters_published
        == chapters_total
    )


def create_detected_chapter_events(
    work_id,
    previous_chapter_count,
    current_chapter_count,
    detected_at,
    chapter_metadata,
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


def create_detected_completion_event(
    work_id,
    previous_chapters_published,
    previous_chapters_total,
    current_chapters_published,
    current_chapters_total,
    completed_date,
    detected_at,
    chapter_metadata,
):
    previous_complete = is_complete(
        previous_chapters_published,
        previous_chapters_total,
    )

    current_complete = is_complete(
        current_chapters_published,
        current_chapters_total,
    )

    if previous_complete:
        return 0

    if not current_complete:
        return 0

    # No previous live observation means we
    # cannot claim we detected a transition.
    if previous_chapters_published is None:
        return 0

    print(
        "  Work completion detected: "
        f"{previous_chapters_published}/"
        f"{previous_chapters_total} -> "
        f"{current_chapters_published}/"
        f"{current_chapters_total}"
    )

    if event_type_exists(
        work_id,
        "work_completed",
    ):
        print(
            "  Work completion event "
            "already exists; skipping."
        )
        return 0

    if completed_date:
        occurred_at = completed_date

        date_source = (
            "ao3_completed"
        )

        date_precision = "date"

    else:
        final_chapter = None

        for chapter in chapter_metadata:
            if (
                chapter.get(
                    "chapter_number"
                )
                == current_chapters_published
            ):
                final_chapter = chapter
                break

        if (
            final_chapter is not None
            and final_chapter.get(
                "published_date"
            )
        ):
            occurred_at = final_chapter[
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

    add_event(
        work_id=work_id,
        occurred_at=occurred_at,
        event_type="work_completed",
        description=(
            "Automatically detected when "
            "AO3 changed the work to complete."
        ),
        source="ao3_detected",
        date_source=date_source,
        date_precision=date_precision,
        detected_at=detected_at,
    )

    if date_precision == "date":
        print(
            "  Added work completion event "
            f"using AO3 date {occurred_at}."
        )

    else:
        print(
            "  Added work completion event "
            "using collection timestamp."
        )

    return 1


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

        (
            previous_chapters_published,
            previous_chapters_total,
        ) = get_latest_public_chapter_state(
            work_id
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

        current_chapters_published = (
            stats.get(
                "chapters_published"
            )
        )

        current_chapters_total = (
            stats.get(
                "chapters_total"
            )
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
            f"{current_chapters_published}"
            "/"
            f"{current_chapters_total}"
        )

        save_snapshot(
            work_id,
            stats,
            source="ao3_public",
            collected_at=detected_at,
        )

        saved += 1

        chapter_increase = (
            previous_chapters_published
            is not None
            and current_chapters_published
            is not None
            and current_chapters_published
            > previous_chapters_published
        )

        previous_complete = is_complete(
            previous_chapters_published,
            previous_chapters_total,
        )

        current_complete = is_complete(
            current_chapters_published,
            current_chapters_total,
        )

        completion_transition = (
            previous_chapters_published
            is not None
            and not previous_complete
            and current_complete
        )

        chapter_metadata = []

        if (
            chapter_increase
            or (
                completion_transition
                and not stats.get(
                    "completed_date"
                )
            )
        ):
            try:
                chapter_metadata = (
                    fetch_chapter_metadata(
                        url
                    )
                )

            except Exception as error:
                print(
                    "  Could not retrieve AO3 "
                    "chapter metadata: "
                    f"{error}"
                )

                print(
                    "  Event dates will fall "
                    "back to collection time "
                    "where necessary."
                )

        try:
            new_events = (
                create_detected_chapter_events(
                    work_id=work_id,
                    previous_chapter_count=(
                        previous_chapters_published
                    ),
                    current_chapter_count=(
                        current_chapters_published
                    ),
                    detected_at=detected_at,
                    chapter_metadata=(
                        chapter_metadata
                    ),
                )
            )

            events_created += new_events

        except Exception as error:
            print(
                "  Snapshot saved, but chapter "
                f"event detection failed: {error}"
            )

        try:
            new_events = (
                create_detected_completion_event(
                    work_id=work_id,
                    previous_chapters_published=(
                        previous_chapters_published
                    ),
                    previous_chapters_total=(
                        previous_chapters_total
                    ),
                    current_chapters_published=(
                        current_chapters_published
                    ),
                    current_chapters_total=(
                        current_chapters_total
                    ),
                    completed_date=stats.get(
                        "completed_date"
                    ),
                    detected_at=detected_at,
                    chapter_metadata=(
                        chapter_metadata
                    ),
                )
            )

            events_created += new_events

        except Exception as error:
            print(
                "  Snapshot saved, but work "
                f"completion detection failed: "
                f"{error}"
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
        f"  Events created: "
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