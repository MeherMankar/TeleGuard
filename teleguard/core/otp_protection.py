from datetime import datetime, timezone


def otp_expiry_fields(expires_at: int) -> dict[str, int | datetime]:
    timestamp = int(expires_at)
    return {
        "expires_at": timestamp,
        "expires_at_dt": datetime.fromtimestamp(timestamp, tz=timezone.utc),
    }
