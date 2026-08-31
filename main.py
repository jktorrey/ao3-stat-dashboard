from database import (
    initialize_database,
    add_work,
    get_all_works,
    update_work,
    save_snapshot,
    get_snapshots_for_work,
)

from collector import fetch_work_stats


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


def view_snapshots():
    works = list_works()

    work_id = input(
        "Enter the number of the work to view: "
    ).strip()

    selected_work = None

    for work in works:
        if str(work[0]) == work_id:
            selected_work = work
            break

    if selected_work is None:
        print("Work not found.")
        print()
        return

    _, _, title, _ = selected_work

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


def main():
    initialize_database()

    print("AO3 Stats Dashboard")
    print()

    while True:
        print("1. Add work")
        print("2. List works")
        print("3. Edit work")
        print("4. Fetch and save current stats")
        print("5. View snapshots")
        print("6. Exit")
        print()

        choice = input("Choose an option: ").strip()
        print()

        if choice == "1":
            ao3_work_id = input("AO3 work ID: ").strip()
            title = input("Title: ").strip()

            add_work(ao3_work_id, title)

            print(f'Added "{title}" to the database.')
            print()

        elif choice == "2":
            list_works()

        elif choice == "3":
            works = list_works()

            work_id = input(
                "Enter the number of the work to edit: "
            ).strip()

            selected_work = None

            for work in works:
                if str(work[0]) == work_id:
                    selected_work = work
                    break

            if selected_work is None:
                print("Work not found.")
                print()
                continue

            _, current_ao3_work_id, current_title, _ = selected_work

            print("Press Enter to keep the current value.")
            print()

            new_ao3_work_id = input(
                f"AO3 work ID [{current_ao3_work_id}]: "
            ).strip()

            new_title = input(
                f"Title [{current_title}]: "
            ).strip()

            if not new_ao3_work_id:
                new_ao3_work_id = current_ao3_work_id

            if not new_title:
                new_title = current_title

            update_work(
                work_id,
                new_ao3_work_id,
                new_title,
            )

            print(f'Updated "{new_title}".')
            print()

        elif choice == "4":
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

        elif choice == "5":
            view_snapshots()

        elif choice == "6":
            print("Goodbye.")
            break

        else:
            print("Invalid option.")
            print()


if __name__ == "__main__":
    main()