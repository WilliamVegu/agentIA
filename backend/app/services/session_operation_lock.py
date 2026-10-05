"""Process and thread exclusion for a session, released by the OS after a crash."""
import hashlib
import os
import threading
import time
from pathlib import Path


class SessionOperationLock:
    def __init__(self, session_id):
        from app.config import settings
        self.path = Path(settings.WORKSPACE_DIR).resolve() / '.operation-locks' / (
            hashlib.sha256(session_id.encode()).hexdigest() + '.lock')
        self._thread = threading.Lock()
        self._handle = None

    def acquire(self, blocking=True, timeout=-1):
        acquired = self._thread.acquire(blocking, timeout) if blocking else self._thread.acquire(False)
        if not acquired:
            return False
        handle = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_symlink() or self.path.parent.is_symlink():
                raise ValueError('Ruta de bloqueo enlazada no admitida')
            handle = self.path.open('a+b')
            if self.path.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            start = time.monotonic()
            while True:
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._handle = handle
                    return True
                except OSError:
                    if not blocking or timeout >= 0 and time.monotonic() - start >= timeout:
                        handle.close()
                        self._thread.release()
                        return False
                    time.sleep(.05)
        except BaseException:
            if handle is not None:
                handle.close()
            self._thread.release()
            raise

    def release(self):
        handle, self._handle = self._handle, None
        if handle is None:
            raise RuntimeError('Lock not held')
        try:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._thread.release()

    def locked(self):
        if self._thread.locked():
            return True
        if not self.acquire(False):
            return True
        self.release()
        return False
