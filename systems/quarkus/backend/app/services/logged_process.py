"""Stream merged command output without storing an unbounded process transcript."""
import codecs
import subprocess
import threading
import os
import time
from collections import deque


class CommandCancelled(RuntimeError):
    pass


def _terminate_owned(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        # The PID was created by this call; never enumerate or kill unrelated processes.
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=5, check=False)
        if result.returncode and process.poll() is None:
            process.kill()
    else:
        process.kill()


def run_logged(command, on_line, *, cwd=None, env=None, timeout=600, cancel_event=None):
    if cancel_event is not None and cancel_event.is_set():
        raise CommandCancelled('Comando cancelado antes de iniciarlo.')
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    tail = deque(maxlen=20)
    failures = []
    def read():
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        pending = ''
        truncated = False
        def consume(text):
            nonlocal pending, truncated
            parts = text.split('\n')
            for index, part in enumerate(parts):
                if len(pending) + len(part) > 8192:
                    truncated = True
                pending = (pending + part)[:8192]
                if index < len(parts) - 1:
                    line = pending.rstrip('\r') + (' [truncated]' if truncated else '')
                    if line:
                        on_line(line)
                        tail.append(line[:4000])
                    pending, truncated = '', False
        try:
            while chunk := process.stdout.read1(4096):
                consume(decoder.decode(chunk))
            consume(decoder.decode(b'', final=True) + '\n')
        except Exception as exc:
            failures.append(exc)
            if process.poll() is None:
                process.kill()
    reader = threading.Thread(target=read, daemon=True)
    try:
        reader.start()
        if cancel_event is None:
            process.wait(timeout=timeout)
        else:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancel_event.is_set():
                    raise CommandCancelled('CLI local cancelado; tareas del daemon Docker no confirmadas.')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    process.wait(timeout=min(0.2, remaining))
                except subprocess.TimeoutExpired:
                    pass
            if cancel_event.is_set():
                raise CommandCancelled('CLI local interrumpido; tareas del daemon Docker no confirmadas.')
        reader.join(timeout=5)
        if reader.is_alive():
            raise RuntimeError('La salida del comando no terminó dentro del límite.')
        if failures:
            raise failures[0]
        if process.returncode:
            from app.services.secret_redaction import redact
            raise RuntimeError(f'Docker exit code {process.returncode}: ' + redact('\n'.join(tail))[-2000:])
        return process.returncode
    finally:
        if process.poll() is None:
            _terminate_owned(process)
        process.wait(timeout=5)
        if reader.is_alive():
            reader.join(timeout=5)
        process.stdout.close()
