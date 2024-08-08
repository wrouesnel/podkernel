"""Internal implementation of logging configuration."""

import json
import logging
import sys
from typing import Callable

import structlog

DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_FORMAT = "console"
DEFAULT_LOG_DEST = "stderr"

_LOG_FORMATS = {
    "console": structlog.dev.ConsoleRenderer(),
    "kv": structlog.processors.KeyValueRenderer(
        key_order=["event"],
        drop_missing=True,
        sort_keys=True,
    ),
    "json": structlog.processors.JSONRenderer(serializer=json.dumps),
}

_LOG_TARGETS = {
    "stdout": sys.stdout,
    "stderr": sys.stderr,
    "unknown": sys.stderr,
}

# class StructlogHandler(logging.Handler):
#     """
#     Feeds all events back into structlog.
#     """
#     def __init__(self, *args, **kw):
#         super(StructlogHandler, self).__init__(*args, **kw)
#         self._log = structlog.get_logger()
#
#     def emit(self, record):
#         self._log.log(record.levelno, record.msg, name=record.name)

"""Standard logging configuration"""
_logging_configured = False


def configure_logging(log_level: str, log_format: str, log_dest: str) -> None:
    """Run once logging configuration."""
    global _logging_configured

    if _logging_configured is True:
        return

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(remove_positional_args=False),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    pre_chain = [
        # Add the logger name, log level and a timestamp to the event_dict if the log entry
        # is not from structlog.
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    processor = _LOG_FORMATS.get(log_format, "unknown")

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=processor,
        foreign_pre_chain=pre_chain,
    )

    handler = logging.StreamHandler(_LOG_TARGETS.get(log_dest, "unknown"))
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging._nameToLevel[log_level.upper()])

    root_logger.debug(f"Logging configured: {log_level} {log_format} {log_dest}")

    _logging_configured = True


get_logger: Callable[..., structlog.BoundLogger] = structlog.get_logger
"""
Alias get_logger in structlog to encourage structlog usage.
"""

getLogger = get_logger
"""
Alias getLogger and get_logger to this module to try and make people use it.
"""
