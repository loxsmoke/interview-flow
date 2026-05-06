"""Process-only background queue state for AI section work."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.models import new_id


QueueStatus = Literal["queued", "running", "canceling", "canceled", "failed", "completed"]

SECTION_ORDER = {
    "research": 0,
    "interview_intel": 1,
    "jd_decode": 2,
    "resume_tailor": 3,
    "stories": 4,
    "pitch": 5,
    "concerns": 6,
    "salary": 7,
}
CUSTOM_SECTION_ORDER = 1000


def queue_sort_key(section_key: str) -> tuple[int, str]:
    if section_key.startswith("custom:"):
        return (CUSTOM_SECTION_ORDER, section_key)
    return (SECTION_ORDER.get(section_key, CUSTOM_SECTION_ORDER - 1), section_key)


@dataclass
class QueueItem:
    id: str
    state_id: str
    section_key: str
    title: str
    status: QueueStatus = "queued"
    queued_at: str = field(default_factory=lambda: datetime.now().isoformat())
    running_at: str = ""
    completed_at: str = ""
    error: str = ""
    error_detail: str = ""
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    events: list[dict[str, Any]] = field(default_factory=list, repr=False)
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list, repr=False)

    def dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state_id": self.state_id,
            "section_key": self.section_key,
            "title": self.title,
            "status": self.status,
            "queued_at": self.queued_at,
            "running_at": self.running_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "error_detail": self.error_detail,
        }


class QueueManager:
    """In-memory queue manager. Queue state is intentionally lost on process exit."""

    def __init__(self) -> None:
        self._running: QueueItem | None = None
        self._waiting: list[QueueItem] = []
        self._failed: dict[tuple[str, str], QueueItem] = {}
        self._lock = asyncio.Lock()
        self._changed = asyncio.Condition()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return self._snapshot_locked()

    async def enqueue(self, state_id: str, section_key: str, title: str) -> QueueItem:
        async with self._lock:
            existing = self._find_active_locked(state_id, section_key)
            if existing:
                return existing
            item = QueueItem(id=new_id(), state_id=state_id, section_key=section_key, title=title)
            self._failed.pop((state_id, section_key), None)
            self._waiting.append(item)
            self._sort_waiting_locked()
            self._promote_next_locked()
            await self._notify_changed_locked()
            return item

    async def unqueue(self, queue_id: str) -> QueueItem:
        async with self._lock:
            for idx, item in enumerate(self._waiting):
                if item.id == queue_id:
                    item.status = "canceled"
                    item.completed_at = datetime.now().isoformat()
                    self._waiting.pop(idx)
                    await self._notify_changed_locked()
                    return item
            raise KeyError(queue_id)

    async def cancel(self, queue_id: str) -> QueueItem:
        async with self._lock:
            if self._running and self._running.id == queue_id:
                self._running.status = "canceling"
                self._running.cancel_event.set()
                await self._publish_event_locked(self._running, {"type": "canceled"})
                await self._notify_changed_locked()
                return self._running
            for idx, item in enumerate(self._waiting):
                if item.id == queue_id:
                    item.status = "canceled"
                    item.completed_at = datetime.now().isoformat()
                    self._waiting.pop(idx)
                    await self._notify_changed_locked()
                    return item
            raise KeyError(queue_id)

    async def cleanup_state(self, state_id: str) -> None:
        async with self._lock:
            changed = False
            if self._running and self._running.state_id == state_id:
                self._running.status = "canceling"
                self._running.cancel_event.set()
                changed = True
            before = len(self._waiting)
            self._waiting = [item for item in self._waiting if item.state_id != state_id]
            changed = changed or len(self._waiting) != before
            failed_keys = [key for key in self._failed if key[0] == state_id]
            for key in failed_keys:
                del self._failed[key]
                changed = True
            if changed:
                await self._notify_changed_locked()

    async def cleanup_custom_action(self, action_id: str) -> None:
        section_key = f"custom:{action_id}"
        async with self._lock:
            changed = False
            if self._running and self._running.section_key == section_key:
                self._running.status = "canceling"
                self._running.cancel_event.set()
                changed = True
            before = len(self._waiting)
            self._waiting = [item for item in self._waiting if item.section_key != section_key]
            changed = changed or len(self._waiting) != before
            failed_keys = [key for key in self._failed if key[1] == section_key]
            for key in failed_keys:
                del self._failed[key]
                changed = True
            if changed:
                await self._notify_changed_locked()

    async def mark_completed(self, queue_id: str) -> QueueItem:
        async with self._lock:
            item = self._require_running_locked(queue_id)
            item.status = "completed"
            item.completed_at = datetime.now().isoformat()
            await self._publish_event_locked(item, {"type": "queue_status", "status": "completed"})
            self._running = None
            self._promote_next_locked()
            await self._notify_changed_locked()
            return item

    async def mark_failed(self, queue_id: str, error: str, detail: str = "") -> QueueItem:
        async with self._lock:
            item = self._require_running_locked(queue_id)
            item.status = "failed"
            item.completed_at = datetime.now().isoformat()
            item.error = error
            item.error_detail = detail
            await self._publish_event_locked(item, {"type": "error", "message": error, "detail": detail})
            self._failed[(item.state_id, item.section_key)] = item
            self._running = None
            self._promote_next_locked()
            await self._notify_changed_locked()
            return item

    async def mark_canceled(self, queue_id: str) -> QueueItem:
        async with self._lock:
            item = self._require_running_locked(queue_id)
            item.status = "canceled"
            item.completed_at = datetime.now().isoformat()
            await self._publish_event_locked(item, {"type": "canceled"})
            self._running = None
            self._promote_next_locked()
            await self._notify_changed_locked()
            return item

    async def wait_for_change(self, last_version: int) -> tuple[int, dict[str, Any]]:
        async with self._changed:
            await self._changed.wait_for(lambda: getattr(self, "_version", 0) != last_version)
            version = getattr(self, "_version", 0)
        return version, await self.snapshot()

    async def running_item(self) -> QueueItem | None:
        async with self._lock:
            return self._running

    async def publish_event(self, queue_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            item = self._find_by_id_locked(queue_id)
            if not item:
                return
            await self._publish_event_locked(item, event)

    async def subscribe(self, queue_id: str) -> tuple[list[dict[str, Any]], asyncio.Queue[dict[str, Any]]]:
        async with self._lock:
            item = self._find_by_id_locked(queue_id)
            if not item:
                raise KeyError(queue_id)
            subscriber: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            item.subscribers.append(subscriber)
            return list(item.events), subscriber

    async def unsubscribe(self, queue_id: str, subscriber: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            item = self._find_by_id_locked(queue_id)
            if item and subscriber in item.subscribers:
                item.subscribers.remove(subscriber)

    def _snapshot_locked(self) -> dict[str, Any]:
        return {
            "running": self._running.dump() if self._running else None,
            "queued": [item.dump() for item in self._waiting],
            "failed": [item.dump() for item in self._failed.values()],
        }

    def _find_active_locked(self, state_id: str, section_key: str) -> QueueItem | None:
        if self._running and self._running.state_id == state_id and self._running.section_key == section_key:
            return self._running
        return next(
            (
                item for item in self._waiting
                if item.state_id == state_id and item.section_key == section_key
            ),
            None,
        )

    def _sort_waiting_locked(self) -> None:
        self._waiting.sort(key=lambda item: queue_sort_key(item.section_key))

    def _promote_next_locked(self) -> None:
        if self._running or not self._waiting:
            return
        self._running = self._waiting.pop(0)
        self._running.status = "running"
        self._running.running_at = datetime.now().isoformat()

    def _require_running_locked(self, queue_id: str) -> QueueItem:
        if not self._running or self._running.id != queue_id:
            raise KeyError(queue_id)
        return self._running

    def _find_by_id_locked(self, queue_id: str) -> QueueItem | None:
        if self._running and self._running.id == queue_id:
            return self._running
        for item in self._waiting:
            if item.id == queue_id:
                return item
        for item in self._failed.values():
            if item.id == queue_id:
                return item
        return None

    async def _publish_event_locked(self, item: QueueItem, event: dict[str, Any]) -> None:
        item.events.append(event)
        for subscriber in list(item.subscribers):
            await subscriber.put(event)

    async def _notify_changed_locked(self) -> None:
        async with self._changed:
            self._version = getattr(self, "_version", 0) + 1
            self._changed.notify_all()


queue_manager = QueueManager()
