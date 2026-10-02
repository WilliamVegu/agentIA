import asyncio
import threading
from typing import Dict, List, Optional
from app.config import settings

class ConcurrencyQueueManager:
    def __init__(self, max_concurrent: int = settings.MAX_CONCURRENT_SESSIONS):
        self.max_concurrent = max_concurrent
        self.active_sessions: set[str] = set()
        self.waiting_queue: List[str] = []
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._thread_lock = threading.Lock()
        self._thread_semaphore = threading.Semaphore(max_concurrent)

    async def enqueue(self, session_id: str) -> int:
        """Enqueues a session and returns its 1-based position (0 if already active)."""
        async with self._lock:
            if session_id in self.active_sessions:
                return 0
            if session_id not in self.waiting_queue:
                self.waiting_queue.append(session_id)
            return self.waiting_queue.index(session_id) + 1

    async def get_position(self, session_id: str) -> int:
        """Returns 0 if active/not queued, or 1-based index if waiting."""
        async with self._lock:
            if session_id in self.active_sessions:
                return 0
            if session_id in self.waiting_queue:
                return self.waiting_queue.index(session_id) + 1
            return 0

    async def acquire_slot(self, session_id: str):
        """Waits until an execution slot is available and claims it."""
        await self._semaphore.acquire()
        async with self._lock:
            if session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)
            self.active_sessions.add(session_id)

    async def release_slot(self, session_id: str):
        """Releases the execution slot for the next queued session."""
        async with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
                self._semaphore.release()
            elif session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)

    def acquire_slot_sync(self, session_id: str):
        """Synchronously claims an execution slot for background worker threads (H24)."""
        self._thread_semaphore.acquire()
        with self._thread_lock:
            if session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)
            self.active_sessions.add(session_id)

    def release_slot_sync(self, session_id: str):
        """Synchronously releases execution slot when the thread actually exits (H09)."""
        with self._thread_lock:
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
                self._thread_semaphore.release()
            elif session_id in self.waiting_queue:
                self.waiting_queue.remove(session_id)

    async def get_queue_status(self) -> dict:
        async with self._lock:
            return {
                "active_workers": len(self.active_sessions),
                "max_workers": self.max_concurrent,
                "waiting_count": len(self.waiting_queue),
                "waiting_sessions": list(self.waiting_queue)
            }

queue_manager = ConcurrencyQueueManager()
