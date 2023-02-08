from datetime import timedelta
from typing import Optional


def parse_timedelta(args: list[str]) -> Optional[timedelta]:
    quantity, unit = int(args[-1][:-1]), args[-1][-1:]

    if unit == "d":
        return timedelta(days=quantity)
    elif unit == "h":
        return timedelta(hours=quantity)
    elif unit == "m":
        return timedelta(minutes=quantity)
    elif unit == "s":
        return timedelta(seconds=quantity)
