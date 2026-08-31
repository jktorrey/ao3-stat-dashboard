import sqlite3


DATABASE_NAME = "ao3_stats.db"


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

            subscriptions INTEGER,
            total_bookmarks INTEGER,
            comment_threads INTEGER,

            source TEXT NOT NULL,

            FOREIGN KEY (work_id) REFERENCES works(id)
        )
    """)

    connection.commit()
    connection.close()