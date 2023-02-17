from datetime import timedelta
from typing import Optional

TIME_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400
}


def parse_timedelta(args: list[str]) -> Optional[timedelta]:
    try:
        quantity, unit = int(args[-1][:-1]), args[-1][-1:]
    except ValueError:
        return

    if unit == "d":
        return timedelta(days=quantity)
    elif unit == "h":
        return timedelta(hours=quantity)
    elif unit == "m":
        return timedelta(minutes=quantity)
    elif unit == "s":
        return timedelta(seconds=quantity)


def parse_time(arg: str) -> Optional[int]:
    quantity, unit = int(arg[:-1]), arg[-1:]

    try:
        return quantity * TIME_MULTIPLIERS[unit]
    except KeyError:
        return
