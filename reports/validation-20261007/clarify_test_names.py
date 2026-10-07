from pathlib import Path
changes = {
 'test_qe_session_surface.py': {
  'test_a_completed_session_is_listed_at_one_hundred_percent': 'test_completed_without_evidence_is_listed_at_zero_percent',
  'test_a_session_whose_lifecycle_is_complete_is_promoted_to_completed': 'test_reading_artifacts_does_not_promote_an_unverified_session',
 },
 'test_qe_pipeline_autopilot.py': {
  'test_force_starts_a_run_even_while_another_is_alive': 'test_force_refuses_a_run_while_another_writer_is_alive',
  '``force`` is how resume works; without it a paused session could never restart.': 'Force may restart a finished worker, but never interleave two live writers.',
 },
 'test_qe_publish_git.py': {
  'test_a_new_remote_is_created_with_the_authenticated_url': 'test_new_remote_uses_a_clean_url',
  'The create-remote branch: when no origin exists, it is created with the token.': 'A new origin never persists credentials; the subprocess receives them temporarily.',
 },
 'test_test_analysis_service.py': {
  '# Iteration 3 (Permitted and succeeds)': '# The third plan exhausts the budget; it does not assert verification success.',
  '# Iteration 6 (Must raise ValueError / Constitution Principle V Violation)': '# A fourth plan exceeds the three-attempt constitutional limit.',
 },
 'test_routes_tests.py': {'# Simulate 5th iteration failure (Constitutional Exhaustion)': '# Simulate the third failed iteration (constitutional exhaustion).'},
 'test_e2e_flow.py': {'# 4. Trigger iteration 5 and verify BLOCKED state (Principle V: max 5 attempts)': '# 4. A source-only repair records unexecuted tests rather than a verified success.'},
}
for name, replacements in changes.items():
 p=Path('backend/tests')/name
 s=p.read_text(encoding='utf-8')
 for old,new in replacements.items():
  assert old in s,(name,old)
  s=s.replace(old,new)
 p.write_text(s,encoding='utf-8')
