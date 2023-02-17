from dataclasses import dataclass


@dataclass
class DefaultWarnSettings:
    limit = 5
    restriction = "kick"  # One of ban, mute, kick
    time = 0  # Time in seconds for timed restriction (e. g. ban or mute). Value < 30 is considered as infinity
