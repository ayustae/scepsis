from datetime import datetime, timedelta, timezone

from chreos.timestamps import format_timestamp, now


def test_now_is_aware_with_second_precision():
    value = now()
    assert value.tzinfo is not None
    assert value.utcoffset() is not None
    assert value.microsecond == 0


def test_format_timestamp_uses_t_separator_and_offset():
    value = datetime(2026, 9, 21, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    assert format_timestamp(value) == "2026-09-21T10:00:00+02:00"


def test_format_timestamp_utc():
    value = datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc)
    assert format_timestamp(value) == "2026-09-21T08:00:00+00:00"
