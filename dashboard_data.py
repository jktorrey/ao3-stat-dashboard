import sqlite3

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
            description
        FROM events
        WHERE work_id = ?
        ORDER BY occurred_at, id
        """,
        connection,
        params=(work_id,),
    )

    connection.close()

    if not events.empty:
        events["occurred_at"] = pd.to_datetime(
            events["occurred_at"],
            format="mixed",
            utc=True,
        )

    return events