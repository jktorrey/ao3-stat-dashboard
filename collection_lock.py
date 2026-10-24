import json
import os
import socket
import time

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = (
    Path(__file__).resolve().parent
)

LOCK_PATH = (
    PROJECT_DIR
    / ".ao3_collection.lock"
)

STALE_LOCK_SECONDS = 60 * 60


class CollectionAlreadyRunning(
    RuntimeError
):
    pass


def remove_stale_lock():
    try:
        lock_age = (
            time.time()
            - LOCK_PATH.stat().st_mtime
        )

    except FileNotFoundError:
        return

    if lock_age < STALE_LOCK_SECONDS:
        return

    try:
        LOCK_PATH.unlink()

    except FileNotFoundError:
        pass


@contextmanager
def collection_lock():
    remove_stale_lock()

    try:
        file_descriptor = os.open(
            LOCK_PATH,
            (
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY
            ),
            0o600,
        )

    except FileExistsError:
        raise CollectionAlreadyRunning(
            "An AO3 collection is already "
            "in progress."
        )

    try:
        lock_details = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "started_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

        os.write(
            file_descriptor,
            (
                json.dumps(
                    lock_details
                )
                + "\n"
            ).encode(
                "utf-8"
            ),
        )

        os.close(
            file_descriptor
        )

        file_descriptor = None

        yield

    finally:
        if file_descriptor is not None:
            os.close(
                file_descriptor
            )

        try:
            LOCK_PATH.unlink()

        except FileNotFoundError:
            pass