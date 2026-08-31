from database import initialize_database, add_work, get_all_works


def main():
    initialize_database()

    print("AO3 Stats Dashboard")
    print()

    while True:
        print("1. Add work")
        print("2. List works")
        print("3. Exit")
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
            works = get_all_works()

            print(f"Tracking {len(works)} works:")
            print()

            for ao3_work_id, title, url in works:
                print(f"{title}")
                print(f"  Work ID: {ao3_work_id}")
                print(f"  {url}")
                print()

        elif choice == "3":
            print("Goodbye.")
            break

        else:
            print("Invalid option.")
            print()


if __name__ == "__main__":
    main()