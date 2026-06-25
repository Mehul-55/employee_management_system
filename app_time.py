"""
Shared application clock.

All business dates and timestamps should come from MongoDB server time
converted to IST. If MongoDB time is unavailable, fall back to local UTC
converted to IST so every module still uses the same timezone.
"""

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
_SERVER_TIME_CACHE = {
    "checked_at": None,
    "server_now": None,
}
_CACHE_TTL_SECONDS = 30


def trusted_now(client_override=None):
    """
    Return a naive IST datetime from MongoDB server time when available.
    Naive datetimes are kept for compatibility with existing stored fields.
    """
    try:
        local_now = datetime.now(timezone.utc)
        if client_override is None and _SERVER_TIME_CACHE["checked_at"] is not None:
            age = (local_now - _SERVER_TIME_CACHE["checked_at"]).total_seconds()
            if age < _CACHE_TTL_SECONDS and _SERVER_TIME_CACHE["server_now"] is not None:
                return (_SERVER_TIME_CACHE["server_now"] + timedelta(seconds=age)).astimezone(IST).replace(tzinfo=None)

        if client_override is None:
            import db_config
            client = getattr(db_config, "client", None)
        else:
            client = client_override
        if client is not None:
            status = client.admin.command("serverStatus")
            server_now = status.get("localTime")
            if isinstance(server_now, datetime):
                if server_now.tzinfo is None:
                    server_now = server_now.replace(tzinfo=timezone.utc)
                if client_override is None:
                    _SERVER_TIME_CACHE["checked_at"] = local_now
                    _SERVER_TIME_CACHE["server_now"] = server_now
                return server_now.astimezone(IST).replace(tzinfo=None)
    except Exception as exc:
        print(
            f"[TIME WARNING] MongoDB server time unavailable ({exc}). "
            "Falling back to local UTC clock converted to IST."
        )
    return datetime.now(timezone.utc).astimezone(IST).replace(tzinfo=None)


def today_date():
    return trusted_now().date()


def today_iso():
    return today_date().isoformat()


def now_time(include_seconds=False):
    return trusted_now().strftime("%H:%M:%S" if include_seconds else "%H:%M")


def now_stamp():
    return trusted_now().strftime("%Y-%m-%d %H:%M:%S")
