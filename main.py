from database import initialize_database, add_work


def main():
    initialize_database()

    print("AO3 Stats Dashboard")
    print("Enter your works below. Leave the work ID blank when finished.")
    print()

    while True:
        ao3_work_id = input("AO3 work ID: ").strip()

        if not ao3_work_id:
            break

        title = input("Title: ").strip()

        add_work(ao3_work_id, title)

        print(f'Added "{title}" to the database.')
        print()

    print("Finished adding works.")


if __name__ == "__main__":
    main()