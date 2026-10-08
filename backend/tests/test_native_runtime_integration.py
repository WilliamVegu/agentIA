"""Owned native runtime acceptance; cached build inputs required, no live IA calls."""
import os
import pytest
from integration.native_runtime_cases import run_native_case

@pytest.mark.skipif(os.getenv('RUN_NATIVE_RUNTIME')!='1',reason='Explicit owned Docker integration required')
def test_native_two_sessions_collision_restart_and_controls(tmp_path,monkeypatch):
    run_native_case('springboot',tmp_path,monkeypatch)
