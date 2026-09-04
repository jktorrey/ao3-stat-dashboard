import sqlite3
from pathlib import Path
import pandas as pd

from database import DATABASE_NAME


def get_work_count():
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute(
        "SELECT COUNT(*) FROM works"
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


def get_snapshot_count():
    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.execute(
        "SELECT COUNT(*) FROM snapshots"
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


def get_overview_data():
    connection = sqlite3.connect(DATABASE_NAME)

    query = """
        WITH latest_public AS (
            SELECT
                snapshots.*,
                ROW_NUMBER() OVER (
                    PARTITION BY work_id
                    ORDER BY collected_at DESC, id DESC
                ) AS row_number
            FROM snapshots
            WHERE source = 'ao3_public'
        ),
        latest_any AS (
            SELECT
                snapshots.*,
                ROW_NUMBER() OVER (
                    PARTITION BY work_id
                    ORDER BY collected_at DESC, id DESC
                ) AS row_number
            FROM snapshots
        )
        SELECT
            works.id AS work_id,
            works.ao3_work_id,
            works.title,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.hits
                ELSE latest_any.hits
            END AS hits,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.kudos
                ELSE latest_any.kudos
            END AS kudos,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.comments
                ELSE latest_any.comments
            END AS comments,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.public_bookmarks
                ELSE latest_any.public_bookmarks
            END AS public_bookmarks,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.word_count
                ELSE latest_any.word_count
            END AS word_count,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.chapters_published
                ELSE latest_any.chapters_published
            END AS chapters_published,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.chapters_total
                ELSE latest_any.chapters_total
            END AS chapters_total,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.collected_at
                ELSE latest_any.collected_at
            END AS collected_at,

            CASE
                WHEN latest_public.id IS NOT NULL
                    THEN latest_public.source
                ELSE latest_any.source
            END AS source

        FROM works

        LEFT JOIN latest_public
            ON works.id = latest_public.work_id
            AND latest_public.row_number = 1

        LEFT JOIN latest_any
            ON works.id = latest_any.work_id
            AND latest_any.row_number = 1

        ORDER BY works.title
    """

    dataframe = pd.read_sql_query(
        query,
        connection,
    )

    connection.close()

    return dataframe


def get_work_history(work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    query = """
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
        ORDER BY collected_at, id
    """

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(work_id,),
    )

    connection.close()

    if not dataframe.empty:
        dataframe["collected_at"] = pd.to_datetime(
            dataframe["collected_at"],
            format="mixed",
            utc=True,
        )

    return dataframe


def get_latest_private_stats(work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    query = """
        SELECT
            collected_at,
            subscriptions,
            total_bookmarks,
            comment_threads,
            source
        FROM snapshots
        WHERE work_id = ?
          AND source != 'ao3_public'
        ORDER BY collected_at DESC, id DESC
        LIMIT 1
    """

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(work_id,),
    )

    connection.close()

    if dataframe.empty:
        return None

    return dataframe.iloc[0].to_dict()


def get_period_changes(hours):
    connection = sqlite3.connect(DATABASE_NAME)

    query = """
        SELECT
            snapshots.id AS snapshot_id,
            snapshots.work_id,
            works.title,
            snapshots.collected_at,
            snapshots.hits,
            snapshots.kudos,
            snapshots.comments,
            snapshots.public_bookmarks,
            snapshots.source
        FROM snapshots
        JOIN works
            ON works.id = snapshots.work_id
        ORDER BY
            snapshots.work_id,
            snapshots.collected_at,
            snapshots.id
    """

    dataframe = pd.read_sql_query(
        query,
        connection,
    )

    connection.close()

    if dataframe.empty:
        return dataframe

    dataframe["collected_at"] = pd.to_datetime(
        dataframe["collected_at"],
        format="mixed",
        utc=True,
    )

    records = []

    for work_id, history in dataframe.groupby(
        "work_id",
        sort=False,
    ):
        history = history.sort_values(
            by=[
                "collected_at",
                "snapshot_id",
            ]
        )

        public_history = history[
            history["source"] == "ao3_public"
        ]

        if not public_history.empty:
            current = public_history.iloc[-1]
        else:
            current = history.iloc[-1]

        cutoff = (
            current["collected_at"]
            - pd.Timedelta(hours=hours)
        )

        baseline_candidates = history[
            history["collected_at"] <= cutoff
        ]

        record = {
            "work_id": work_id,
            "title": current["title"],
            "current_collected_at": (
                current["collected_at"]
            ),
            "baseline_collected_at": None,
            "baseline_hours": None,
            "hits_change": None,
            "kudos_change": None,
            "comments_change": None,
            "bookmarks_change": None,
        }

        if not baseline_candidates.empty:
            baseline = baseline_candidates.iloc[-1]

            elapsed = (
                current["collected_at"]
                - baseline["collected_at"]
            )

            record["baseline_collected_at"] = (
                baseline["collected_at"]
            )

            record["baseline_hours"] = (
                elapsed.total_seconds() / 3600
            )

            record["hits_change"] = (
                current["hits"]
                - baseline["hits"]
            )

            record["kudos_change"] = (
                current["kudos"]
                - baseline["kudos"]
            )

            record["comments_change"] = (
                current["comments"]
                - baseline["comments"]
            )

            record["bookmarks_change"] = (
                current["public_bookmarks"]
                - baseline["public_bookmarks"]
            )

        records.append(record)

    return pd.DataFrame(records)


def get_work_events(work_id):
    connection = sqlite3.connect(DATABASE_NAME)

    events = pd.read_sql_query(
        """
        SELECT
            id,
            occurred_at,
            event_type,
            chapter_number,
            description,
            source,
            date_source,
            date_precision,
            detected_at
        FROM events
        WHERE work_id = ?
        ORDER BY occurred_at, id
        """,
        connection,
        params=(work_id,),
    )

    connection.close()

    return events


def get_system_health():
    connection = sqlite3.connect(
        DATABASE_NAME
    )

    public_snapshots = pd.read_sql_query(
        """
        SELECT collected_at
        FROM snapshots
        WHERE source = 'ao3_public'
        """,
        connection,
    )

    settings_rows = connection.execute("""
        SELECT key, value
        FROM settings
        WHERE key IN (
            'collection_interval_hours',
            'last_scheduled_collection',
            'last_daily_summary'
        )
    """).fetchall()

    connection.close()

    settings = {
        key: value
        for key, value in settings_rows
    }

    latest_public_snapshot = None

    if not public_snapshots.empty:
        parsed_times = pd.to_datetime(
            public_snapshots[
                "collected_at"
            ],
            format="mixed",
            utc=True,
            errors="coerce",
        )

        parsed_times = (
            parsed_times.dropna()
        )

        if not parsed_times.empty:
            latest_public_snapshot = (
                parsed_times.max()
                .isoformat()
            )

    project_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    backup_dir = (
        project_dir / "backups"
    )

    backup_files = []

    if backup_dir.exists():
        backup_files = sorted(
            backup_dir.glob(
                "ao3_stats_*.db"
            ),
            key=lambda path:
                path.stat().st_mtime,
            reverse=True,
        )

    latest_backup = None
    latest_backup_name = None

    if backup_files:
        latest_backup_file = (
            backup_files[0]
        )

        latest_backup_name = (
            latest_backup_file.name
        )

        latest_backup = pd.Timestamp(
            latest_backup_file
            .stat()
            .st_mtime,
            unit="s",
            tz="UTC",
        ).isoformat()

    log_file = (
        project_dir
        / "logs"
        / "ao3_dashboard.log"
    )

    latest_log_activity = None
    latest_error = None

    if log_file.exists():
        latest_log_activity = (
            pd.Timestamp(
                log_file.stat().st_mtime,
                unit="s",
                tz="UTC",
            )
            .isoformat()
        )

        try:
            with log_file.open(
                "r",
                encoding="utf-8",
            ) as handle:
                lines = handle.readlines()

            for line in reversed(lines):
                if " ERROR " in line:
                    latest_error = (
                        line.strip()
                    )
                    break

        except OSError:
            latest_error = (
                "Could not read operational log."
            )

    interval_value = settings.get(
        "collection_interval_hours"
    )

    try:
        collection_interval = int(
            interval_value
        )

    except (
        TypeError,
        ValueError,
    ):
        collection_interval = None

    return {
        "latest_public_snapshot":
            latest_public_snapshot,

        "last_scheduled_collection":
            settings.get(
                "last_scheduled_collection"
            ),

        "collection_interval_hours":
            collection_interval,

        "last_daily_summary":
            settings.get(
                "last_daily_summary"
            ),

        "latest_backup":
            latest_backup,

        "latest_backup_name":
            latest_backup_name,

        "backup_count":
            len(backup_files),

        "latest_log_activity":
            latest_log_activity,

        "latest_error":
            latest_error,
    }