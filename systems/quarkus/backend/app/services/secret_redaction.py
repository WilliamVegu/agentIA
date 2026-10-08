"""Redact credentials before errors, events or metadata cross a boundary."""
import re

_KEY = re.compile(r'(?i)(?:[a-z]+[_-]?)?(api[_-]?key|authorization|password|access[_-]?token|pat|secret|credential)s?')
_TEXT = re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9_]{16,}|github_pat_[a-z0-9_]{16,})\b')
_URL = re.compile(r'(https?://)[^/\s@]+@')
_HEADER = re.compile(r'(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)[^\s,;]+')


def redact(value):
    if isinstance(value, dict):
        return {str(key): '[REDACTED]' if _KEY.fullmatch(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _HEADER.sub(r'\1[REDACTED]', _URL.sub(r'\1[REDACTED]@', _TEXT.sub('[REDACTED]', value)))
    return value


def without_credentials(value):
    if isinstance(value, dict):
        return {key: without_credentials(item) for key, item in value.items() if not _KEY.fullmatch(str(key))}
    if isinstance(value, (list, tuple)):
        return [without_credentials(item) for item in value]
    return redact(value)
