"""Small in-memory limits for a single-process public demo."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Callable


@dataclass(slots=True)
class RateLimitExceeded(Exception):
    message: str
    retry_after_seconds: int

    def __str__(self) -> str:
        return self.message


class InMemoryRateLimiter:
    """Thread-safe fixed-window limits with bounded per-session histories.

    State is intentionally ephemeral: ModelScope container restarts reset demo
    quotas, just as they reset the live snapshot database.
    """

    def __init__(
        self,
        *,
        ask_per_hour: int = 10,
        refresh_per_hour: int = 3,
        ask_per_day_global: int = 100,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.ask_per_hour = ask_per_hour
        self.refresh_per_hour = refresh_per_hour
        self.ask_per_day_global = ask_per_day_global
        self._clock = clock
        self._events: dict[str, dict[str, deque[float]]] = {
            "ask": defaultdict(deque),
            "refresh": defaultdict(deque),
        }
        self._daily_ask_count: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def check(self, action: str, client_id: str) -> None:
        if action not in self._events:
            raise ValueError(f"unknown rate-limit action: {action}")
        now = self._clock()
        limit = self.ask_per_hour if action == "ask" else self.refresh_per_hour
        with self._lock:
            events = self._events[action][client_id]
            cutoff = now - 3600
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry = max(1, int(events[0] + 3600 - now) + 1)
                raise RateLimitExceeded(
                    f"匿名会话每小时最多{limit}次{self._label(action)}",
                    retry,
                )

            if action == "ask":
                day = datetime.fromtimestamp(now, tz=timezone.utc).date().isoformat()
                if self._daily_ask_count[day] >= self.ask_per_day_global:
                    next_day = (
                        datetime.fromtimestamp(now, tz=timezone.utc)
                        .replace(hour=0, minute=0, second=0, microsecond=0)
                        .timestamp()
                        + 86400
                    )
                    raise RateLimitExceeded(
                        "全站今日 Agent 问题额度已用完",
                        max(1, int(next_day - now) + 1),
                    )
                self._daily_ask_count[day] += 1
                self._prune_daily_counts(day)

            events.append(now)

    @staticmethod
    def _label(action: str) -> str:
        return "提问" if action == "ask" else "实时刷新"

    def _prune_daily_counts(self, current_day: str) -> None:
        for day in list(self._daily_ask_count):
            if day != current_day:
                del self._daily_ask_count[day]
