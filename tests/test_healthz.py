"""/healthz bypasses ALLOWED_HOSTS validation (Fly Consul checker uses raw IP)."""

from __future__ import annotations


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.content == b"ok"


def test_healthz_passes_with_unknown_host(client, settings):
    """Mirrors Fly's internal probe: hits the machine IP directly."""
    settings.ALLOWED_HOSTS = ["ps-tracker.fly.dev"]
    resp = client.get("/healthz", headers={"host": "172.19.24.98:8000"})
    assert resp.status_code == 200
    assert resp.content == b"ok"


def test_non_healthz_path_still_host_validated(client, settings):
    """The bypass is scoped to /healthz only."""
    settings.ALLOWED_HOSTS = ["ps-tracker.fly.dev"]
    settings.DEBUG = False
    resp = client.get("/", headers={"host": "172.19.24.98:8000"})
    assert resp.status_code == 400
