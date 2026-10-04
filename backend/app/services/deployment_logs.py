"""Bounded, atomic deployment history with durable SSE sequence numbers."""
import json
import re
from app.services.local_runtime import record_directory

MAX_ENTRIES = 1000
MAX_MESSAGE = 4000


def redact(message):
    text = str(message)
    text = re.sub(r'(?i)((?:password|token|api[_-]?key|secret)["\']?\s*[=:]\s*)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(\bBearer\s+)\S+', r'\1[REDACTED]', text)
    text = re.sub(r'(://)[^\s/@:]+:[^\s/@]+@', r'\1[REDACTED]@', text)
    return text[:MAX_MESSAGE]


def load(session_id):
    path = record_directory(session_id) / 'logs.json'
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'version': 1, 'nextId': 1, 'entries': []}
    # Read the previous string-only format without discarding existing evidence.
    if isinstance(raw, list) and all(isinstance(line, str) for line in raw):
        raw = {'version': 1, 'nextId': len(raw) + 1,
               'entries': [{'id': i + 1, 'message': line} for i, line in enumerate(raw)]}
    if not isinstance(raw, dict) or raw.get('version') != 1:
        raise ValueError('Historial de logs inválido; no se reiniciarán sus IDs.')
    entries, next_id = raw.get('entries'), raw.get('nextId')
    if not isinstance(entries, list) or type(next_id) is not int or next_id < 1:
        raise ValueError('Historial de logs inválido; no se reiniciarán sus IDs.')
    previous = None
    for entry in entries:
        if (not isinstance(entry, dict) or type(entry.get('id')) is not int
                or entry['id'] < 1 or entry['id'] >= next_id
                or not isinstance(entry.get('message'), str)
                or (previous is not None and entry['id'] != previous + 1)):
            raise ValueError('Historial de logs inválido; no se reiniciarán sus IDs.')
        previous = entry['id']
    if (entries and entries[-1]['id'] != next_id - 1) or (not entries and next_id != 1):
        raise ValueError('Historial de logs inválido; no se reiniciarán sus IDs.')
    return {'version': 1, 'nextId': next_id,
            'entries': [{'id': e['id'], 'message': redact(e['message'])} for e in entries[-MAX_ENTRIES:]]}


def append(session_id, history, message):
    """Caller holds the shared lock; publish memory only after atomic disk commit."""
    updated = {'version': 1, 'nextId': history['nextId'] + 1,
               'entries': (history['entries'] + [{'id': history['nextId'], 'message': redact(message)}])[-MAX_ENTRIES:]}
    directory = record_directory(session_id)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / 'logs.tmp'
    temporary.write_text(json.dumps(updated, ensure_ascii=False), encoding='utf-8')
    temporary.replace(directory / 'logs.json')
    return updated


def frames(history, cursor):
    """Return retained records after cursor, explicitly signalling a history gap."""
    newest = history['nextId'] - 1
    oldest = history['entries'][0]['id'] if history['entries'] else 1
    if cursor > newest or (cursor > 0 and cursor < oldest - 1):
        reason = 'cursor_ahead' if cursor > newest else 'history_truncated'
        cursor = oldest - 1
        yield cursor, f'id: {cursor}\nevent: log-reset\ndata: {json.dumps({"reason": reason, "firstAvailableId": oldest})}\n\n'
    for entry in history['entries']:
        if entry['id'] > cursor:
            cursor = entry['id']
            yield cursor, f'id: {cursor}\ndata: {json.dumps(entry["message"], ensure_ascii=False)}\n\n'
