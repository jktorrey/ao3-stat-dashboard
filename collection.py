from database import (
    initialize_database,
    get_all_works,
    save_snapshot,
)

from collector import fetch_work_stats


def collect_all_stats():
    works = get_all_works()

    saved_count = 0
    error_count = 0

    for work_id, ao3_work_id, title, url in works:
        print(f"Fetching {title}...")

        try:
            stats = fetch_work_stats(url)

            print(f"  Hits: {stats.get('hits')}")
            print(f"  Kudos: {stats.get('kudos')}")
            print(f"  Comments: {stats.get('comments')}")
            print(
                f"  Bookmarks: "
                f"{stats.get('public_bookmarks')}"
            )
            print(f"  Words: {stats.get('word_count')}")
            print(
                f"  Chapters: "
                f"{stats.get('chapters_published')}/"
                f"{stats.get('chapters_total')}"
            )

            save_snapshot(
                work_id,
                stats,
                source="ao3_public",
            )

            saved_count += 1

            print("  Snapshot saved.")
            print()

        except Exception as error:
            error_count += 1

            print(f"  ERROR: {error}")
            print("  Snapshot not saved.")
            print()

    print("Collection complete.")
    print(f"  Snapshots saved: {saved_count}")
    print(f"  Errors: {error_count}")
    print()

    return saved_count, error_count


def main():
    initialize_database()
    collect_all_stats()


if __name__ == "__main__":
    main()