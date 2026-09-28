"""Stage execution boundary for feature 011 (LLM-Driven Generation Stages).

This package owns the concerns that must not be duplicated per stage or per
execution path: instruction loading and revisioning, compliance gating,
correction-journal accumulation, and stage dispatch.

See specs/011-llm-generation-nodes/contracts/stage-execution.md.
"""
