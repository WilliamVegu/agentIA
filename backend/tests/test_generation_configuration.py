"""A broken or missing model configuration must not silently emit offline sources."""
import pytest
from app.orchestrator.stages.runner import select_generation_mode
from app.services.llm_factory import LLMFactory

@pytest.mark.parametrize('provider',[None,'deepseek'])
def test_missing_credential_does_not_choose_offline(provider):
    with pytest.raises(ValueError,match='modo offline'):
        select_generation_mode(provider=provider)

@pytest.mark.parametrize('failure',[False,True])
def test_unconstructible_client_does_not_choose_offline(monkeypatch,failure):
    def client(**kwargs):
        if failure: raise RuntimeError('private-provider-sentinel')
        return None
    monkeypatch.setattr(LLMFactory,'get_chat_model',client)
    with pytest.raises(ValueError) as observed:
        select_generation_mode(api_key='test-model-credential',provider='deepseek')
    assert 'private-provider-sentinel' not in str(observed.value)

@pytest.mark.parametrize('options',[{'provider':'mock'},{'force_deterministic':True},{'offline_requested':True}])
def test_explicit_offline_choice_remains_available(options):
    assert select_generation_mode(**options).mode=='DETERMINISTIC'

@pytest.mark.parametrize('credential',['sk-realistic-mock-substring','ordinary-key-containing-mock'])
def test_key_substring_is_not_an_offline_selection(monkeypatch,credential):
    monkeypatch.setattr(LLMFactory,'get_chat_model',lambda **kwargs:None)
    with pytest.raises(ValueError):
        select_generation_mode(api_key=credential,provider='deepseek')
