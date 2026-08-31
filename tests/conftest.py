"""Pytest fixtures: isolated data dir + fake DNS so no real network in tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, fetcher, services


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Each test gets a fresh data dir and no real DNS / network."""
    config.configure(data_dir=tmp_path / "data")
    # Stub DNS resolution: return a public TEST-NET-3 IP so the SSRF guard's
    # DNS check never hits the network. SSRF tests re-patch this locally.
    monkeypatch.setattr(fetcher, "_resolve", lambda host, port: ["203.0.113.42"])
    # Default: API create/update paths won't hit the network. Tests that
    # exercise the real fetcher pipeline build a mock fetcher themselves.
    async def _fake_meta(url, fetcher=None):
        return {"title": "", "description": "", "logo": None, "ext": None, "source": ""}
    monkeypatch.setattr(services, "_fetch_meta", _fake_meta)
    yield
    config.settings.logo_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def client():
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c
