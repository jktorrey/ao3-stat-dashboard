import sqlite3

from database import DATABASE_NAME


AO3_WORK_ID = 91487606
COLLECTED_AT = "2026-08-01T17:00:00+00:00"


connection = sqlite3.connect(DATABASE_NAME)

cursor = connection.execute("""
    SELECT
        snapshots.id,
        works.title,
        snapshots.collected_at,
        snapshots.hits,
        snapshots.kudos,
        snapshots.source
    FROM snapshots
    JOIN works
        ON works.id = snapshots.work_id
    WHERE works.ao3_work_id = ?
      AND snapshots.collected_at = ?
""", (
    AO3_WORK_ID,
    COLLECTED_AT,
))

matches = cursor.fetchall()

if not matches:
    print("No matching snapshot found.")
    connection.close()
    raise SystemExit


print("Matching snapshot(s):")
print()

for row in matches:
    snapshot_id, title, collected_at, hits, kudos, source = row

    print(f"Snapshot ID: {snapshot_id}")
    print(f"Work: {title}")
    print(f"Collected: {collected_at}")
    print(f"Hits: {hits}")
    print(f"Kudos: {kudos}")
    print(f"Source: {source}")
    print()


confirmation = input(
    "Type DELETE to remove this snapshot: "
).strip()


if confirmation == "DELETE":
    snapshot_ids = [
        (row[0],)
        for row in matches
    ]

    connection.executemany(
        "DELETE FROM snapshots WHERE id = ?",
        snapshot_ids,
    )

    connection.commit()

    print(
        f"Deleted {len(snapshot_ids)} snapshot(s)."
    )

else:
    print("Deletion cancelled.")


connection.close()