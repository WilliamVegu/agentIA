"""Exact deterministic output revisions, with immutable historical baselines.

The reliability fixture declares valid annotation parameters explicitly. Captured
expectations are separate from historical evidence and never rewritten by tests.
Incomplete historical declarations must be rejected rather than guessed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.stages import journal as journal_mod  # noqa: E402
from app.orchestrator.stages.runner import STAGE_ORDER, run_stages  # noqa: E402
from app.services.llm_factory import LLMFactory  # noqa: E402

BASELINE_JSON = REPO_ROOT / "reports" / "baselines" / "011-pre-migration-generation-baseline.json"
CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "reliability_blueprints"


def _sha256(text: str) -> str:
    """Must match the digest the capture script recorded."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _assert_recorded_hash(path: Path, expected: str) -> None:
    """Git may check text out with LF or CRLF; retain strict content identity."""
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    assert expected in {hashlib.sha256(value).hexdigest()
                        for value in (raw, lf, lf.replace(b"\n", b"\r\n"))}


@pytest.fixture(scope="module")
def baseline() -> dict:
    revisions=REPO_ROOT/'backend/tests/fixtures/reliability_generation_revisions.json'
    recorded=json.loads(revisions.read_text(encoding='utf-8'))
    assert recorded['formatVersion']==1
    _assert_recorded_hash(BASELINE_JSON, recorded['historicalBaselineSha256'])
    for entry in recorded['per_blueprint']:
        name=entry['blueprint_id']+'.json'
        original=REPO_ROOT/'backend/tests/fixtures/baseline_blueprints'/name
        _assert_recorded_hash(original, entry['historicalInputSha256'])
        _assert_recorded_hash(CORPUS_DIR/name, entry['inputSha256'])
        for path,item in entry['comparison_subset_content'].items():
            assert _sha256(item['content'])==item['sha256']==entry['artifact_digests'][path]
    return recorded


@pytest.fixture(scope="module")
def corpus() -> dict:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_DIR.glob("*.json"))
    }


def _run_offline(blueprint: dict, workspace: Path) -> dict:
    """Run the five stages through the seam in DETERMINISTIC mode."""
    state = {
        "session_id": f"parity-{blueprint.get('blueprintId', 'x')}",
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "generation_mode": journal_mod.GENERATION_MODE_DETERMINISTIC,
    }
    return run_stages(state, stages=STAGE_ORDER)


def test_offline_sessions_require_no_credentials(baseline, corpus, tmp_path, monkeypatch):
    """FR-013 / SC-004: no model client is constructed on the offline path.

    Proven by making client construction explode: if the deterministic path ever
    tried to build a model client, this test would fail rather than silently
    passing through a fallback.
    """
    def _explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("the deterministic path must not construct a model client")

    monkeypatch.setattr(LLMFactory, "get_chat_model", _explode)

    blueprint = corpus["minimal"]
    workspace = tmp_path / "minimal"
    workspace.mkdir()
    result = _run_offline(blueprint, workspace)

    assert result["generated_files"], "offline path produced no artifacts"
    assert result.get("status") != "BLOCKED"


def test_offline_output_matches_explicit_reliability_revision(baseline, corpus, tmp_path):
    """SC-004: byte-for-byte parity with the pre-migration baseline."""
    by_id = {entry["blueprint_id"]: entry for entry in baseline["per_blueprint"]}

    compared = 0
    for blueprint_id, blueprint in corpus.items():
        expected = by_id.get(blueprint_id)
        if expected is None or expected.get("terminal_status") != "COMPLETED":
            continue

        workspace = tmp_path / blueprint_id
        workspace.mkdir()
        result = _run_offline(blueprint, workspace)

        actual_files = {
            path.relative_to(workspace).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(workspace.rglob("*"))
            if path.is_file()
        }
        actual_digests = {p: _sha256(c) for p, c in actual_files.items()}

        assert set(actual_digests) == set(expected["artifact_digests"]), (
            f"{blueprint_id}: artifact path set drifted from the frozen baseline"
        )
        mismatched = [
            p for p in actual_digests
            if actual_digests[p] != expected["artifact_digests"][p]
        ]
        assert not mismatched, (
            f"{blueprint_id}: content differs from the frozen baseline for {mismatched}"
        )
        compared += 1

    assert compared >= 4, f"expected to compare at least 4 blueprints, compared {compared}"


def test_offline_comparison_subset_content_is_identical(baseline, corpus, tmp_path):
    """The designated comparison subset is what SC-001 reads.

    Comparing the retained content — not just digests — is what makes this a
    parity check rather than a difference check.
    """
    by_id = {entry["blueprint_id"]: entry for entry in baseline["per_blueprint"]}
    checked = 0

    for blueprint_id, blueprint in corpus.items():
        expected = by_id.get(blueprint_id)
        if expected is None or expected.get("terminal_status") != "COMPLETED":
            continue

        workspace = tmp_path / f"subset-{blueprint_id}"
        workspace.mkdir()
        _run_offline(blueprint, workspace)

        for rel_path, record in (expected.get("comparison_subset_content") or {}).items():
            produced = workspace / rel_path
            assert produced.is_file(), f"{blueprint_id}: {rel_path} missing from offline output"
            assert produced.read_text(encoding="utf-8") == record["content"], (
                f"{blueprint_id}: {rel_path} differs from the retained baseline content"
            )
            checked += 1

    assert checked > 0, "no comparison-subset content was checked"


def test_offline_journal_records_no_corrections_and_no_requests(baseline, corpus, tmp_path):
    """The offline path consumes no model requests and applies no gate.

    This is the deliberate asymmetry from FR-013, asserted rather than assumed.
    """
    for blueprint_id, blueprint in corpus.items():
        workspace = tmp_path / f"journal-{blueprint_id}"
        workspace.mkdir()
        result = _run_offline(blueprint, workspace)

        journal = result["generation_journal"]
        assert journal["generation_mode"] == journal_mod.GENERATION_MODE_DETERMINISTIC
        assert journal["total_requests"] == 0, f"{blueprint_id}: offline path spent model requests"
        assert journal["provider"] is None and journal["model"] is None, (
            f"{blueprint_id}: a deterministic session must not record a provider or model"
        )
        assert len(journal["entries"]) == len(STAGE_ORDER)

        for entry in journal["entries"]:
            assert entry["outcome"] == journal_mod.OUTCOME_SUCCEEDED
            assert entry["request_count"] == 0
            assert entry["correction_attempts"] == []
            assert entry["initial_verdict"] is None


def test_offline_provenance_has_no_provider_or_model(baseline, corpus, tmp_path):
    """FR-019: provenance is recorded, but offline sessions carry no model identity."""
    workspace = tmp_path / "provenance"
    workspace.mkdir()
    result = _run_offline(corpus["minimal"], workspace)

    records = result["artifact_provenance"]
    assert records, "no provenance was recorded for the offline path"
    assert {r["artifact_path"] for r in records} == set(result["generated_files"])
    for record in records:
        assert record["generation_mode"] == journal_mod.GENERATION_MODE_DETERMINISTIC
        assert record["provider"] is None
        assert record["model"] is None


@pytest.mark.parametrize('name',['constrained','pair-b'])
def test_historical_incomplete_annotations_remain_rejected_and_unchanged(baseline,name):
    from app.services.domain_descriptor import normalize_blueprint
    original=REPO_ROOT/'backend/tests/fixtures/baseline_blueprints'/(name+'.json')
    payload=json.loads(original.read_text(encoding='utf-8'))
    with pytest.raises(ValueError,match='sin parámetros'):
        normalize_blueprint(payload)
    entry=next(item for item in baseline['per_blueprint'] if item['blueprint_id']==name)
    assert hashlib.sha256(original.read_bytes()).hexdigest()==entry['historicalInputSha256']
