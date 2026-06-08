from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import IntFlag, auto


class DebugLevel(IntFlag):
    VERBOSE = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


DEFAULT_VISIBLE_LEVELS = DebugLevel.WARNING | DebugLevel.ERROR
ALL_LEVELS = DebugLevel.VERBOSE | DebugLevel.INFO | DebugLevel.WARNING | DebugLevel.ERROR
LEVEL_ORDER = (DebugLevel.VERBOSE, DebugLevel.INFO, DebugLevel.WARNING, DebugLevel.ERROR)


@dataclass(frozen=True)
class DebugMessage:
    timestamp: datetime
    level: DebugLevel
    message: str

    def text(self) -> str:
        return f"{self.timestamp:%H:%M:%S.%f}"[:-3] + f" [{self.level.name}] {self.message}"


class DebugLog:
    def __init__(self, max_entries: int = 3000) -> None:
        self.max_entries = max_entries
        self.entries: deque[DebugMessage] = deque(maxlen=max_entries)

    def add(self, level: DebugLevel, message: str) -> DebugMessage:
        entry = DebugMessage(datetime.now(), level, message)
        self.entries.append(entry)
        return entry
