from datetime import datetime
from pathlib import Path
import sqlite3

from tzlocal import get_localzone

from database import DATABASE_NAME


PROJECT_DIR = Path(__file__).resolve().parent

BACKUP_DIR = PROJECT_DIR / "backups"

BACKUP_PREFIX = "ao3_stats_"

BACKUPS_TO_KEEP = 30

LOCAL_TIMEZONE = get_localzone()


def get_backups():
    if not BACKUP_DIR.exists():
        return []

    return sorted(
        BACKUP_DIR.glob(
            f"{BACKUP_PREFIX}*.db"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def backup_exists_for_today():
    today = datetime.now(
        LOCAL_TIMEZONE
    ).strftime(
        "%Y-%m-%d"
    )

    pattern = (
        f"{BACKUP_PREFIX}"
        f"{today}_*.db"
    )

    return any(
        BACKUP_DIR.glob(pattern)
    )


def remove_old_backups():
    backups = get_backups()

    old_backups = backups[
        BACKUPS_TO_KEEP:
    ]

    for backup_path in old_backups:
        backup_path.unlink()

        print(
            "Removed old database backup: "
            f"{backup_path.name}"
        )

    return len(old_backups)


def backup_database(
    force=False,
):
    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        not force
        and backup_exists_for_today()
    ):
        print(
            "Database backup already exists "
            "for today; skipping."
        )

        return {
            "created": False,
            "path": None,
            "removed": 0,
        }

    now = datetime.now(
        LOCAL_TIMEZONE
    )

    timestamp = now.strftime(
        "%Y-%m-%d_%H%M%S"
    )

    backup_path = (
        BACKUP_DIR
        / (
            f"{BACKUP_PREFIX}"
            f"{timestamp}.db"
        )
    )

    source_connection = None
    backup_connection = None

    try:
        source_connection = (
            sqlite3.connect(
                DATABASE_NAME
            )
        )

        backup_connection = (
            sqlite3.connect(
                backup_path
            )
        )

        source_connection.backup(
            backup_connection
        )

    except Exception:
        if backup_path.exists():
            backup_path.unlink()

        raise

    finally:
        if backup_connection is not None:
            backup_connection.close()

        if source_connection is not None:
            source_connection.close()

    removed = remove_old_backups()

    print(
        "Database backup created: "
        f"{backup_path.name}"
    )

    return {
        "created": True,
        "path": backup_path,
        "removed": removed,
    }


def main():
    try:
        backup_database()

    except Exception as error:
        print(
            f"Database backup failed: "
            f"{error}"
        )


if __name__ == "__main__":
    main()