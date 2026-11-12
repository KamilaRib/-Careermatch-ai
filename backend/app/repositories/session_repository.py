"""Session repository abstraction.

The MVP uses an in-memory store with TTL. The `SessionRepository` protocol allows a
future PostgreSQL/Supabase implementation without touching business logic.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SessionData:
    session_id: str
    csrf_token: str
    created_at: float
    last_seen: float
    # Arbitrary per-session state (resume, job, analyses, chat history...).
    store: dict[str, Any] = field(default_factory=dict)


class SessionRepository(Protocol):
    def create(self, session_id: str, csrf_token: str) -> SessionData: ...
    def get(self, session_id: str) -> SessionData | None: ...
    def touch(self, session_id: str) -> None: ...
    def delete(self, session_id: str) -> bool: ...
    def purge_expired(self) -> int: ...
    def count(self) -> int: ...


class InMemorySessionRepository:
    """Thread-safe in-memory sessions with sliding expiration."""

    def __init__(self, ttl_seconds: int, clock: Any = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._data: dict[str, SessionData] = {}
        self._lock = threading.RLock()

    def _expired(self, s: SessionData) -> bool:
        return self._clock() - s.last_seen > self._ttl

    def create(self, session_id: str, csrf_token: str) -> SessionData:
        now = self._clock()
        s = SessionData(session_id=session_id, csrf_token=csrf_token, created_at=now, last_seen=now)
        with self._lock:
            self._data[session_id] = s
        return s

    def get(self, session_id: str) -> SessionData | None:
        with self._lock:
            s = self._data.get(session_id)
            if s is None:
                return None
            if self._expired(s):
                self._data.pop(session_id, None)
                s.store.clear()
                return None
            return s

    def touch(self, session_id: str) -> None:
        with self._lock:
            s = self._data.get(session_id)
            if s:
                s.last_seen = self._clock()

    def delete(self, session_id: str) -> bool:
        with self._lock:
            s = self._data.pop(session_id, None)
            if s:
                s.store.clear()
            return s is not None

    def purge_expired(self) -> int:
        with self._lock:
            expired = [k for k, s in self._data.items() if self._expired(s)]
            for k in expired:
                self._data.pop(k).store.clear()
            return len(expired)

    def count(self) -> int:
        with self._lock:
            return len(self._data)


async def run_periodic_cleanup(repo: SessionRepository, interval_seconds: int) -> None:
    from app.core.logging import get_logger

    log = get_logger("app.sessions.cleanup")
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            removed = repo.purge_expired()
            if removed:
                log.info("sessions_purged", extra={"removed": removed, "active": repo.count()})
        except Exception as exc:  # pragma: no cover - defensive
            log.error("session_cleanup_failed", extra={"exc_type": type(exc).__name__})
