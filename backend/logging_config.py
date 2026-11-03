"""Central logging setup for the Classroom Engagement backend.

Call ``setup_logging()`` once, as early as possible (app.py does this before
any other project module is imported). Every other module then just does::

    import logging
    logger = logging.getLogger(__name__)

Environment variables
---------------------
LOG_LEVEL      DEBUG, INFO (default), WARNING, ERROR
LOG_DIR        folder for log files (default: backend/logs)
LOG_TO_FILE    set to "0" to log to the console only
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "logs",
)

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(threadName)s | %(message)s"
)

_configured = False


def setup_logging():
    """Configure the root logger once (safe to call multiple times)."""
    global _configured

    if _configured:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if os.environ.get("LOG_TO_FILE", "1") != "0":
        log_dir = os.environ.get("LOG_DIR", _DEFAULT_LOG_DIR)

        try:
            os.makedirs(log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                os.path.join(log_dir, "backend.log"),
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)

        except OSError as exc:
            # Never stop the server just because the log folder is
            # read-only; console logging still works.
            root.warning("File logging disabled: %s", exc)

    # Keep third-party libraries from flooding the log at DEBUG level.
    for noisy in ("werkzeug", "urllib3", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(max(level, logging.INFO))

    _configured = True
