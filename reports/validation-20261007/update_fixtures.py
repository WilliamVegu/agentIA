from pathlib import Path

BASE = Path('backend/tests')
def edit(name, old, new):
    p = BASE / name
    content = p.read_text(encoding='utf-8')
    if old not in content:
        raise ValueError(f'Missing text in {name}: {old[:70]}')
    p.write_text(content.replace(old, new), encoding='utf-8')

edit('test_app_examples.py', '    values.update(overrides)\n', '    values.update(overrides)\n')
edit('test_app_examples.py', '        db.merge(GenerationSessionDB(**values))\n        db.commit()', '        db.merge(GenerationSessionDB(**values))\n        db.commit()\n        if values["status"] == SessionStatus.COMPLETED:\n            from _support import source_delivery\n            source_delivery(session_id)')
edit('test_app_examples.py', 'assert "Quality Gate is BLOCKED" in export.json()["detail"]', 'assert "SAST" in export.json()["detail"]')
edit('test_app_examples.py', 'assert not (tmp_path / session_id / "docker-compose.yml").exists()', 'assert not any(e.step == "DevOps & Manifiestos" for e in pipeline_runner._event_queues[session_id].queue)')
edit('test_qe_session_surface.py', 'rawText="algo"', 'rawText="Crear un servicio de pedidos con nombre y total"')
edit('test_qe_session_surface.py', '    assert listed.completion_percentage == 100.0\n    assert listed.status == SessionStatus.COMPLETED\n    assert _row(SESSION_ID).current_lifecycle_phase == "COMPLETED"', '    assert listed.completion_percentage < 100.0\n    assert listed.status == SessionStatus.RUNNING\n    assert _row(SESSION_ID).current_lifecycle_phase == "INITIAL"')
edit('test_qe_session_surface.py', '    _make_session(SESSION_ID, status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED)\n\n    items', '    _make_session(SESSION_ID, status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED)\n\n    items')
edit('test_qe_session_surface.py', '    assert listed.completion_percentage == 100.0', '    assert listed.completion_percentage == 0.0  # a status label alone is not verification evidence')
edit('test_qe_session_surface.py', '    async def fake_release(session_id):', '    def fake_release(session_id):')
edit('test_qe_session_surface.py', 'rs.queue_manager.release_slot = fake_release', 'rs.queue_manager.cancel_waiting = fake_release')
edit('test_qe_session_surface.py', 'del rs.queue_manager.release_slot', 'del rs.queue_manager.cancel_waiting')
edit('test_routes_security.py', '    # Verify session audit endpoint', '    from _support import source_delivery\n    source_delivery(session_id)\n\n    # Verify session audit endpoint')
edit('test_routes_security.py', '"Quality Gate is BLOCKED"', '"SAST"')
edit('test_routes_devops.py', '            spec_name="order-service",', '            spec_name="order-service",\n            database_engine="POSTGRESQL",')
edit('test_qe_deploy_docker.py', '["docker", "compose", "-p", SESSION_ID, "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180"]', '["docker", "compose", "-p", SESSION_ID, "-f", "docker-compose.yml", "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180"]')
# Shared instructions can mention annotations even when the blueprint does not.
edit('test_generation_stages_model.py', '        assert rule not in requests["pair-a"]', '        assert requests["pair-b"].count(rule) > requests["pair-a"].count(rule)')
edit('test_test_analysis_service.py', 'test_execute_repair_iteration_and_cap_at_5', 'test_execute_repair_iteration_and_cap_at_3')
edit('test_test_analysis_service.py', 'assert iter1.outcome == RepairOutcome.SUCCESS', 'assert iter1.outcome == RepairOutcome.FAILED_CONTINUE  # a patch plan is not an executed test')
edit('test_test_analysis_service.py', 'assert iter3.outcome == RepairOutcome.SUCCESS', 'assert iter3.outcome == RepairOutcome.FAILED_BLOCKED')
p = BASE / 'test_test_analysis_service.py'
content = p.read_text(encoding='utf-8')
start = content.index('    # Iteration 5 (Exhaustion cap)')
end = content.index('    # Iteration 6', start)
content = content[:start] + content[end:]
content = content.replace('iteration_number=6', 'iteration_number=4').replace('hard-capped at 5 iterations', 'hard-capped at 3 iterations')
p.write_text(content, encoding='utf-8')
# Lifecycle fixtures explicitly complete source generation; no synthetic real tests.
edit('test_qe_lifecycle_rules.py', '    (ws / "src" / "main" / "java" / "App.java").write_text("class App {}", encoding="utf-8")', '    (ws / "src" / "main" / "java" / "App.java").write_text("class App {}", encoding="utf-8")\n    from app.services.verification_policy import workspace_fingerprint\n    with SessionLocal() as db:\n        row = db.get(GenerationSessionDB, ws.name)\n        if row.status not in (SessionStatus.BLOCKED, SessionStatus.CANCELLED):\n            row.status = SessionStatus.COMPLETED\n            row.verification_metrics_json = json.dumps({"sourceDeliveryReady": True, "sourceDeliveryFingerprint": workspace_fingerprint(ws)})\n            db.commit()')
# Source-delivery fixtures must be resealed after their Compose input changes.
edit('test_qe_lifecycle_rules.py', '    (ws / "docker-compose.yml").write_text("services: {}", encoding="utf-8")', '    (ws / "docker-compose.yml").write_text("services: {}", encoding="utf-8")\n    from _support import source_delivery\n    source_delivery(session_id, ws)')
