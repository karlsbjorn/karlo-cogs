from datetime import datetime, timedelta, timezone


def get_timeout_timestamp() -> int:
    """
    Get the timestamp for the next 180 second interval.

    :return: The timestamp as an integer.
    """
    now = datetime.now(tz=timezone.utc)
    timeout = now + timedelta(seconds=180)
    return int(timeout.timestamp())
