import pytest
from pathlib import Path
from app.services.git_service import prepare_authenticated_url, sanitize_git_url

def test_prepare_authenticated_url():
    raw_url = "https://github.com/my-org/my-repo.git"
    auth_url = prepare_authenticated_url(raw_url, "ghp_secretToken123")
    assert "ghp_secretToken123" in auth_url
    assert "@github.com/my-org/my-repo.git" in auth_url

def test_sanitize_git_url_strips_token():
    auth_url = "https://oauth2:ghp_secretToken123@github.com/my-org/my-repo.git"
    clean_url = sanitize_git_url(auth_url)
    assert "ghp_secretToken123" not in clean_url
    assert clean_url == "https://github.com/my-org/my-repo.git"

