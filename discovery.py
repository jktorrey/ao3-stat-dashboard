from datetime import datetime, timezone

from collector import (
    fetch_user_works,
    fetch_work_stats,
    fetch_chapter_metadata,
)

from database import (
    initialize_database,
    get_all_works,
    get_work_by_ao3_id,
    add_work,
    save_snapshot,
    add_event,
    event_type_exists,
    chapter_event_exists,
)


AO3_USERNAME = "like_a_ghoulboss"


def backfill_discovered_events(
    work_id,
    stats,
    chapters,
):
    events_created = 0

    published_date = stats.get(
        "published_date"
    )

    if (
        published_date
        and not event_type_exists(
            work_id,
            "work_published",
        )
    ):
        add_event(
            work_id=work_id,
            occurred_at=published_date,
            event_type="work_published",
            description=(
                "Publication date retrieved "
                "from AO3 when the work was "
                "first discovered."
            ),
            source="ao3_backfill",
            date_source="ao3_published",
            date_precision="date",
        )

        events_created += 1

        print(
            f"    Publication event: "
            f"{published_date}"
        )

    for chapter in chapters:
        chapter_number = chapter.get(
            "chapter_number"
        )

        if (
            chapter_number is None
            or chapter_number == 1
        ):
            continue

        if chapter_event_exists(
            work_id,
            chapter_number,
        ):
            continue

        chapter_date = chapter.get(
            "published_date"
        )

        if not chapter_date:
            continue

        chapter_title = chapter.get(
            "title"
        )

        if chapter_title:
            description = (
                f"{chapter_title} — "
                "Publication date retrieved "
                "from AO3 when the work was "
                "first discovered."
            )

        else:
            description = (
                "Publication date retrieved "
                "from AO3 when the work was "
                "first discovered."
            )

        add_event(
            work_id=work_id,
            occurred_at=chapter_date,
            event_type="chapter_published",
            chapter_number=chapter_number,
            description=description,
            source="ao3_backfill",
            date_source="ao3_chapter_date",
            date_precision="date",
        )

        events_created += 1

        print(
            f"    Chapter {chapter_number}: "
            f"{chapter_date}"
        )

    chapters_published = stats.get(
        "chapters_published"
    )

    chapters_total = stats.get(
        "chapters_total"
    )

    work_is_complete = (
        chapters_published is not None
        and chapters_total is not None
        and chapters_published
        == chapters_total
    )

    # A one-chapter work is already represented
    # by its publication event. A separate
    # completion marker would add no useful
    # information to the chart.
    should_add_completion = (
        work_is_complete
        and chapters_published > 1
        and not event_type_exists(
            work_id,
            "work_completed",
        )
    )

    if should_add_completion:
        completed_date = stats.get(
            "completed_date"
        )

        date_source = None

        if completed_date:
            completion_date = (
                completed_date
            )

            date_source = (
                "ao3_completed"
            )

        else:
            final_chapter = None

            for chapter in chapters:
                if (
                    chapter.get(
                        "chapter_number"
                    )
                    == chapters_published
                ):
                    final_chapter = chapter
                    break

            if (
                final_chapter is not None
                and final_chapter.get(
                    "published_date"
                )
            ):
                completion_date = (
                    final_chapter[
                        "published_date"
                    ]
                )

                date_source = (
                    "ao3_chapter_date"
                )

            else:
                completion_date = None

        if completion_date:
            add_event(
                work_id=work_id,
                occurred_at=completion_date,
                event_type="work_completed",
                description=(
                    "Completion date retrieved "
                    "from AO3 when the work was "
                    "first discovered."
                ),
                source="ao3_backfill",
                date_source=date_source,
                date_precision="date",
            )

            events_created += 1

            print(
                "    Completion event: "
                f"{completion_date}"
            )

    return events_created


def initialize_discovered_work(work):
    ao3_work_id = work[
        "ao3_work_id"
    ]

    title = work["title"]
    url = work["url"]

    print()
    print(
        f'  Initializing "{title}"...'
    )

    # Fetch the live work page before making
    # any database changes. If AO3 is having
    # trouble, we leave SQLite untouched and
    # can simply discover the work again later.
    try:
        stats = fetch_work_stats(
            url
        )

    except Exception as error:
        print(
            "    Could not retrieve initial "
            f"stats: {error}"
        )

        print(
            "    Work was not added."
        )

        return False

    chapters = []

    chapters_published = stats.get(
        "chapters_published"
    )

    if (
        chapters_published is not None
        and chapters_published > 1
    ):
        try:
            chapters = (
                fetch_chapter_metadata(
                    url
                )
            )

        except Exception as error:
            print(
                "    Could not retrieve "
                "chapter metadata: "
                f"{error}"
            )

            print(
                "    The work will still be "
                "added; historical chapter "
                "events can be backfilled "
                "later."
            )

    add_work(
        ao3_work_id,
        title,
    )

    saved_work = get_work_by_ao3_id(
        ao3_work_id
    )

    if saved_work is None:
        print(
            "    Work was added, but could "
            "not be read back from SQLite."
        )

        return False

    work_id = saved_work[0]

    collected_at = datetime.now(
        timezone.utc
    )

    save_snapshot(
        work_id,
        stats,
        source="ao3_public",
        collected_at=collected_at,
    )

    print(
        "    Initial snapshot saved."
    )

    try:
        events_created = (
            backfill_discovered_events(
                work_id,
                stats,
                chapters,
            )
        )

        print(
            f"    Historical events added: "
            f"{events_created}"
        )

    except Exception as error:
        print(
            "    Work and snapshot were saved, "
            "but event backfill failed: "
            f"{error}"
        )

        print(
            "    Events can be backfilled "
            "later from the CLI."
        )

    print(
        "    Initialization complete."
    )

    return True


def discover_and_add_new_works():
    initialize_database()

    print(
        f"Checking AO3 works for "
        f"{AO3_USERNAME}..."
    )
    print()

    try:
        ao3_works = fetch_user_works(
            AO3_USERNAME
        )

    except Exception as error:
        print(
            f"Discovery failed: {error}"
        )
        print()

        return {
            "found": 0,
            "new": 0,
            "added": 0,
            "failed": 0,
        }

    tracked_works = get_all_works()

    tracked_ids = {
        int(work[1])
        for work in tracked_works
    }

    new_works = [
        work
        for work in ao3_works
        if work["ao3_work_id"]
        not in tracked_ids
    ]

    already_tracked = [
        work
        for work in ao3_works
        if work["ao3_work_id"]
        in tracked_ids
    ]

    print(
        f"AO3 works found: "
        f"{len(ao3_works)}"
    )

    print(
        f"Already tracked: "
        f"{len(already_tracked)}"
    )

    print(
        f"New works: "
        f"{len(new_works)}"
    )

    if not new_works:
        print()
        print(
            "No new works found."
        )
        print()

        return {
            "found": len(ao3_works),
            "new": 0,
            "added": 0,
            "failed": 0,
        }

    print()
    print("NEW:")
    print()

    for work in new_works:
        print(
            f"  {work['title']}"
        )

        print(
            "    Work ID: "
            f"{work['ao3_work_id']}"
        )

    print()
    print(
        "Initializing new works..."
    )

    added = 0
    failed = 0

    for work in new_works:
        success = initialize_discovered_work(
            work
        )

        if success:
            added += 1

        else:
            failed += 1

    print()
    print("Discovery complete.")
    print(
        f"  New works found: "
        f"{len(new_works)}"
    )
    print(
        f"  Added: {added}"
    )
    print(
        f"  Failed: {failed}"
    )
    print()

    return {
        "found": len(ao3_works),
        "new": len(new_works),
        "added": added,
        "failed": failed,
    }


def main():
    discover_and_add_new_works()


if __name__ == "__main__":
    main()