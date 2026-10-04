"""A user's execution choice is independent of host capabilities and test evidence."""
from enum import Enum


class ExecutionMode(str, Enum):
    SOURCE_ONLY = "SOURCE_ONLY"
    DOCKER = "DOCKER"


class VerificationOutcome(str, Enum):
    NOT_RUN = "NOT_RUN"
    SKIPPED_BY_CHOICE = "SKIPPED_BY_CHOICE"
    ENVIRONMENT_UNAVAILABLE = "ENVIRONMENT_UNAVAILABLE"
    PASSED = "PASSED"
    FAILED = "FAILED"
    OUTDATED = "OUTDATED"
