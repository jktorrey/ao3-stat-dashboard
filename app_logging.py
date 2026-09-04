import logging
import sys
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

LOG_DIR = PROJECT_DIR / "logs"

LOG_FILE = LOG_DIR / "ao3_dashboard.log"

MAX_LOG_BYTES = 2 * 1024 * 1024

BACKUP_COUNT = 5


class TeeStream:
    def __init__(
        self,
        original_stream,
        logger,
        level,
    ):
        self.original_stream = (
            original_stream
        )

        self.logger = logger
        self.level = level

        self.buffer = ""

    def write(self, text):
        self.original_stream.write(
            text
        )

        self.original_stream.flush()

        self.buffer += text

        while "\n" in self.buffer:
            line, self.buffer = (
                self.buffer.split(
                    "\n",
                    1,
                )
            )

            if line.strip():
                self.logger.log(
                    self.level,
                    line,
                )

    def flush(self):
        self.original_stream.flush()

        if self.buffer.strip():
            self.logger.log(
                self.level,
                self.buffer,
            )

        self.buffer = ""

    def isatty(self):
        return self.original_stream.isatty()


def get_file_logger():
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = logging.getLogger(
        "ao3_dashboard_file"
    )

    logger.setLevel(
        logging.INFO
    )

    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )

        formatter = logging.Formatter(
            "%(asctime)s "
            "%(levelname)s "
            "%(message)s"
        )

        handler.setFormatter(
            formatter
        )

        logger.addHandler(
            handler
        )

        logger.propagate = False

    return logger


@contextmanager
def capture_output():
    logger = get_file_logger()

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    stdout_tee = TeeStream(
        original_stdout,
        logger,
        logging.INFO,
    )

    stderr_tee = TeeStream(
        original_stderr,
        logger,
        logging.ERROR,
    )

    sys.stdout = stdout_tee
    sys.stderr = stderr_tee

    try:
        yield

    except Exception:
        logger.exception(
            "Unhandled exception"
        )

        raise

    finally:
        stdout_tee.flush()
        stderr_tee.flush()

        sys.stdout = original_stdout
        sys.stderr = original_stderr