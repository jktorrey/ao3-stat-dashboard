import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATABASE_NAME = Path(__file__).resolve().parent / "ao3_stats.db"


def initialize_database():
    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY,
            ao3_work_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY,
            work_id INTEGER NOT NULL,
            collected_at TEXT NOT NULL,

            hits INTEGER,
            kudos INTEGER,
            comments INTEGER,
            public_bookmarks INTEGER,
            word_count INTEGER,
            chapters_published INTEGER,
            chapters_total INTEGER,

            subscriptions INTEGER,
            total_bookmarks INTEGER,
            comment_threads INTEGER,

            source TEXT NOT NULL,

            FOREIGN KEY (work_id) REFERENCES works(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            work_id INTEGER NOT NULL,
            occurred_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            chapter_number INTEGER,
            description TEXT,

            FOREIGN KEY (work_id) REFERENCES works(id)
        )
    """)

    cursor = connection.execute(
        "PRAGMA table_info(snapshots)"
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "chapters_total" not in columns:
        connection.execute(
            "ALTER TABLE snapshots "
            "ADD COLUMN chapters_total INTEGER"
        )

    connection.execute("""
        INSERT OR IGNORE INTO settings (
            key,
            value
        )
        VALUES (
            'collection_interval_hours',
            '6'
        )
    """)

    connection.commit()
    connection.close()


def add_work(ao3_work_id, title):
    url = f"https://archiveofourown.org/works/{ao3_work_id}"

    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        INSERT INTO works (ao3_work_id, title, url)
        VALUES (?, ?, ?)
    """, (ao3_work_id, title, url))

    connection.commit()
    connection.close()


def get_all_works():
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute(
        "SELECT id, ao3_work_id, title, url "
        "FROM works "
        "ORDER BY title"
    )

    works = cursor.fetchall()

    connection.close()

    return works


def update_work(work_id, ao3_work_id, title):
    url = f"https://archiveofourown.org/works/{ao3_work_id}"

    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        UPDATE works
        SET ao3_work_id = ?, title = ?, url = ?
        WHERE id = ?
    """, (ao3_work_id, title, url, work_id))

    connection.commit()
    connection.close()


def save_snapshot(
    work_id,
    stats,
    source="ao3_public",
    collected_at=None,
):
    if collected_at is None:
        collected_at = datetime.now(timezone.utc)

    if isinstance(collected_at, datetime):
        collected_at = collected_at.isoformat()

    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        INSERT INTO snapshots (
            work_id,
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
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        work_id,
        collected_at,
        stats.get("hits"),
        stats.get("kudos"),
        stats.get("comments"),
        stats.get("public_bookmarks"),
        stats.get("word_count"),
        stats.get("chapters_published"),
        stats.get("chapters_total"),
        stats.get("subscriptions"),
        stats.get("total_bookmarks"),
        stats.get("comment_threads"),
        source,
    ))

    connection.commit()
    connection.close()


def get_snapshots_for_work(work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT
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
            source
        FROM snapshots
        WHERE work_id = ?
        ORDER BY collected_at DESC
    """, (work_id,))

    snapshots = cursor.fetchall()

    connection.close()

    return snapshots


def get_collection_interval():
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT value
        FROM settings
        WHERE key = 'collection_interval_hours'
    """)

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return 6

    return float(row[0])


def set_collection_interval(hours):
    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        INSERT INTO settings (key, value)
        VALUES ('collection_interval_hours', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (str(hours),))

    connection.commit()
    connection.close()


def get_last_scheduled_collection():
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT value
        FROM settings
        WHERE key = 'last_scheduled_collection'
    """)

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return datetime.fromisoformat(row[0])


def set_last_scheduled_collection(timestamp=None):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        INSERT INTO settings (key, value)
        VALUES ('last_scheduled_collection', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (timestamp.isoformat(),))

    connection.commit()
    connection.close()


def get_work_by_ao3_id(ao3_work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT id, ao3_work_id, title, url
        FROM works
        WHERE ao3_work_id = ?
    """, (ao3_work_id,))

    work = cursor.fetchone()

    connection.close()

    return work


def snapshot_exists(work_id, collected_at):
    if isinstance(collected_at, datetime):
        collected_at = collected_at.isoformat()

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT 1
        FROM snapshots
        WHERE work_id = ?
          AND collected_at = ?
        LIMIT 1
    """, (
        work_id,
        collected_at,
    ))

    exists = cursor.fetchone() is not None

    connection.close()

    return exists


def find_redundant_snapshots():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row

    cursor = connection.execute("""
        SELECT
            snapshots.id AS snapshot_id,
            snapshots.work_id,
            works.title,
            snapshots.collected_at,
            snapshots.hits,
            snapshots.kudos,
            snapshots.comments,
            snapshots.public_bookmarks,
            snapshots.word_count,
            snapshots.chapters_published,
            snapshots.chapters_total,
            snapshots.subscriptions,
            snapshots.total_bookmarks,
            snapshots.comment_threads,
            snapshots.source
        FROM snapshots
        JOIN works
            ON works.id = snapshots.work_id
        ORDER BY
            snapshots.work_id,
            snapshots.collected_at,
            snapshots.id
    """)

    rows = cursor.fetchall()
    connection.close()

    stat_fields = (
        "hits",
        "kudos",
        "comments",
        "public_bookmarks",
        "word_count",
        "chapters_published",
        "chapters_total",
        "subscriptions",
        "total_bookmarks",
        "comment_threads",
    )

    redundant = []

    previous_stats = {}
    previous_keeper = {}

    for row in rows:
        work_id = row["work_id"]

        current_stats = tuple(
            row[field]
            for field in stat_fields
        )

        if (
            work_id not in previous_stats
            or current_stats != previous_stats[work_id]
        ):
            previous_stats[work_id] = current_stats
            previous_keeper[work_id] = row
            continue

        keeper = previous_keeper[work_id]

        redundant.append({
            "snapshot_id": row["snapshot_id"],
            "work_id": work_id,
            "title": row["title"],
            "keep_collected_at": keeper["collected_at"],
            "keep_source": keeper["source"],
            "remove_collected_at": row["collected_at"],
            "remove_source": row["source"],
        })

    return redundant


def delete_snapshots(snapshot_ids):
    if not snapshot_ids:
        return 0

    connection = sqlite3.connect(DATABASE_NAME)

    connection.executemany(
        "DELETE FROM snapshots WHERE id = ?",
        [(snapshot_id,) for snapshot_id in snapshot_ids],
    )

    connection.commit()
    connection.close()

    return len(snapshot_ids)


def get_null_stat_counts():
    connection = sqlite3.connect(DATABASE_NAME)

    stat_fields = (
        "hits",
        "kudos",
        "comments",
        "public_bookmarks",
        "word_count",
        "chapters_published",
        "chapters_total",
        "subscriptions",
        "total_bookmarks",
        "comment_threads",
    )

    counts = {}

    for field in stat_fields:
        cursor = connection.execute(
            f"SELECT COUNT(*) FROM snapshots "
            f"WHERE {field} IS NULL"
        )

        counts[field] = cursor.fetchone()[0]

    connection.close()

    return counts


def replace_null_stats_with_zero():
    counts = get_null_stat_counts()
    values_replaced = sum(counts.values())

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT COUNT(*)
        FROM snapshots
        WHERE
            hits IS NULL
            OR kudos IS NULL
            OR comments IS NULL
            OR public_bookmarks IS NULL
            OR word_count IS NULL
            OR chapters_published IS NULL
            OR chapters_total IS NULL
            OR subscriptions IS NULL
            OR total_bookmarks IS NULL
            OR comment_threads IS NULL
    """)

    rows_updated = cursor.fetchone()[0]

    connection.execute("""
        UPDATE snapshots
        SET
            hits = COALESCE(hits, 0),
            kudos = COALESCE(kudos, 0),
            comments = COALESCE(comments, 0),
            public_bookmarks = COALESCE(public_bookmarks, 0),
            word_count = COALESCE(word_count, 0),
            chapters_published = COALESCE(chapters_published, 0),
            chapters_total = COALESCE(chapters_total, 0),
            subscriptions = COALESCE(subscriptions, 0),
            total_bookmarks = COALESCE(total_bookmarks, 0),
            comment_threads = COALESCE(comment_threads, 0)
    """)

    connection.commit()
    connection.close()

    return {
        "rows_updated": rows_updated,
        "values_replaced": values_replaced,
    }


def add_event(
    work_id,
    occurred_at,
    event_type,
    chapter_number=None,
    description=None,
):
    if isinstance(occurred_at, datetime):
        occurred_at = occurred_at.isoformat()

    connection = sqlite3.connect(DATABASE_NAME)

    connection.execute("""
        INSERT INTO events (
            work_id,
            occurred_at,
            event_type,
            chapter_number,
            description
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        work_id,
        occurred_at,
        event_type,
        chapter_number,
        description,
    ))

    connection.commit()
    connection.close()


def get_events_for_work(work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute("""
        SELECT
            id,
            occurred_at,
            event_type,
            chapter_number,
            description
        FROM events
        WHERE work_id = ?
        ORDER BY occurred_at, id
    """, (work_id,))

    events = cursor.fetchall()

    connection.close()

    return events