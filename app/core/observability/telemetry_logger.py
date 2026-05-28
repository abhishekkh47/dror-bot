import json

from app.utils.logger import logger


def log_telemetry_event(
    telemetry_event,
):
    """
    Emit orchestration telemetry.
    """

    logger.info(
        "RAG_TELEMETRY",
        extra={
            "telemetry":
                json.dumps(
                    telemetry_event
                )
        }
    )