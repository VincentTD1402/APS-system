import logging

from .config import settings

LOG_LEVEL = settings.LOG_LEVEL.upper()


class _RequestIdFilter(logging.Filter):
    """Inject the current request id (or '-') into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.services.llm.concurrency import request_id_var

            record.request_id = request_id_var.get() or "-"
        except Exception:
            record.request_id = "-"
        return True


_root = logging.getLogger()
if not getattr(_root, "_aps_request_id_configured", False):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [rid=%(request_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        force=True,
    )
    _root.addFilter(_RequestIdFilter())
    for h in _root.handlers:
        h.addFilter(_RequestIdFilter())
    _root._aps_request_id_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
