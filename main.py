from database import (
    initialize_database,
    add_work,
    get_all_works,
    update_work,
)


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


def main():
    initialize_database()

    print("AO3 Stats Dashboard")
    print()

    while True:
        print("1. Add work")
        print("2. List works")
        print("3. Edit work")
        print("4. Exit")
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

            work_id = input("Enter the number of the work to edit: ").strip()

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
            print("Goodbye.")
            break

        else:
            print("Invalid option.")
            print()


if __name__ == "__main__":
    main()