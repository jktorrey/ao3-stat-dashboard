from collector import fetch_user_works

from database import (
    initialize_database,
    get_all_works,
)


AO3_USERNAME = "like_a_ghoulboss"


def check_for_new_works():
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
        return

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

    print()

    if new_works:
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

            print(
                f"    {work['url']}"
            )

            print()

    else:
        print(
            "No new works found."
        )
        print()

    return new_works


def main():
    check_for_new_works()


if __name__ == "__main__":
    main()