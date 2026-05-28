import json

from app.utils.logger import logger


def log_telemetry_event(telemetry_event):
    """
    Emit orchestration telemetry (sync).
    """
    logger.info(
        "RAG_TELEMETRY",
        extra={
            "telemetry": json.dumps(telemetry_event)
        },
    )


async def async_log_telemetry_event(telemetry_event):
    """
    Emit orchestration telemetry (async-compatible).
    Logging itself is CPU-bound and fast, so this
    wraps the sync call for use with create_task.
    """
    log_telemetry_event(telemetry_event)
