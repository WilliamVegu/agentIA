import asyncio
import threading
from app.config import settings


class ConcurrencyQueueManager:
    """One FIFO capacity shared by asynchronous and threaded workers."""
    def __init__(self, max_concurrent=settings.MAX_CONCURRENT_SESSIONS):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be positive")
        self.max_concurrent = max_concurrent
        self.active_sessions = set()
        self.waiting_queue = []
        self._condition = threading.Condition()
        self._cancelled = set()

    async def enqueue(self, session_id):
        with self._condition:
            self._cancelled.discard(session_id)
            if session_id in self.active_sessions:
                return 0
            if session_id not in self.waiting_queue:
                self.waiting_queue.append(session_id)
            return self.waiting_queue.index(session_id) + 1

    async def get_position(self, session_id):
        with self._condition:
            return self.waiting_queue.index(session_id) + 1 if session_id in self.waiting_queue else 0

    def _claim(self, session_id):
        if session_id in self._cancelled:
            return False
        if session_id in self.active_sessions:
            raise RuntimeError("Session already has an active worker")
        if session_id not in self.waiting_queue:
            self.waiting_queue.append(session_id)
        if self.waiting_queue[0] == session_id and len(self.active_sessions) < self.max_concurrent:
            self.waiting_queue.pop(0)
            self.active_sessions.add(session_id)
            return True
        return None

    async def acquire_slot(self, session_id):
        try:
            while True:
                with self._condition:
                    claimed = self._claim(session_id)
                if claimed is not None:
                    return claimed
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            self.cancel_waiting(session_id)
            raise

    def acquire_slot_sync(self, session_id, cancel_event=None):
        with self._condition:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self.cancel_waiting(session_id)
                    return False
                claimed = self._claim(session_id)
                if claimed is not None:
                    return claimed
                self._condition.wait(0.05)

    def try_acquire_slot_sync(self, session_id):
        with self._condition:
            if session_id in self.active_sessions or self.waiting_queue or len(self.active_sessions) >= self.max_concurrent:
                return False
            self._cancelled.discard(session_id)
            self.active_sessions.add(session_id)
            return True

    def reset_cancellation(self, session_id):
        with self._condition:
            if session_id not in self.active_sessions:
                self._cancelled.discard(session_id)

    def cancel_waiting(self, session_id):
        with self._condition:
            self._cancelled.add(session_id)
            if session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)
            self._condition.notify_all()

    def release_slot_sync(self, session_id):
        with self._condition:
            self.active_sessions.discard(session_id)
            if session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)
            self._condition.notify_all()

    async def release_slot(self, session_id):
        self.release_slot_sync(session_id)

    async def get_queue_status(self):
        with self._condition:
            return {"active_workers": len(self.active_sessions), "max_workers": self.max_concurrent,
                    "waiting_count": len(self.waiting_queue), "waiting_sessions": list(self.waiting_queue)}


queue_manager = ConcurrencyQueueManager()
