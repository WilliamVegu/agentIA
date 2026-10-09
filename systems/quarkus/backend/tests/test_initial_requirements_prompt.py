import asyncio
import pytest
from test_draft_authority import session
from integration.reliability_fixtures import ledger_draft
from app.api.routes_requirements import get_session_requirements
from app.services.workspace_guard import atomic_write_workspace_file


def test_initial_prompt_survives_requirements_reload_without_inventing_draft(session):
    prompt = '# Registro contable\n\nRegistrar asientos con correo válido e importe positivo.'
    atomic_write_workspace_file('draft-authority', 'spec.md', prompt)
    first = asyncio.run(get_session_requirements('draft-authority'))
    second = asyncio.run(get_session_requirements('draft-authority'))
    assert first == second
    assert first['rawPrompt'] == prompt
    assert first['hasDraft'] is False and first['revisionId'] is None


def test_saved_revision_remains_authoritative_for_requirements_prompt(session):
    from app.services.draft_revision_service import save_revision
    draft = ledger_draft()
    draft['markdownSpec'] = '# Revisión aprobable del libro contable'
    revision = save_revision('draft-authority', draft)
    atomic_write_workspace_file('draft-authority', 'spec.md', 'obsolete projection')
    result = asyncio.run(get_session_requirements('draft-authority'))
    assert result['rawPrompt'] == draft['markdownSpec']
    assert result['revisionId'] == revision['revisionId']


def test_initial_prompt_refuses_link_to_file_outside_workspace(session, tmp_path):
    from fastapi import HTTPException
    session.mkdir()
    outside = tmp_path / 'private.md'
    outside.write_text('private sentinel', encoding='utf-8')
    try:
        (session / 'spec.md').symlink_to(outside)
    except OSError:
        pytest.skip('Symlink creation unavailable on this host')
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_session_requirements('draft-authority'))
    assert error.value.status_code == 400
