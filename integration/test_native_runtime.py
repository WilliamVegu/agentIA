"""Cross-studio owned Docker acceptance. Opt in with RUN_NATIVE_RUNTIME=1."""
import os
from pathlib import Path
import pytest
from integration.reliability_smoke import run_suite

@pytest.mark.skipif(os.environ.get('RUN_NATIVE_RUNTIME')!='1',reason='Requires prepared native caches and explicit Docker opt-in')
@pytest.mark.parametrize('studio',['springboot','quarkus'])
def test_native_runtime_journey(studio,tmp_path):
    assert run_suite('runtime',tmp_path/'isolated',tmp_path/'evidence',(studio,),docker=True)==0
