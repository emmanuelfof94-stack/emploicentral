"""Init Sentry conditionnelle (core/observability.py)."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from core import observability

FAKE_DSN = "https://publickey@o0.ingest.sentry.io/0"  # format valide, aucune valeur réelle


def test_no_dsn_means_no_sentry(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    # Si le SDK était importé malgré tout, cette entrée provoquerait une ImportError.
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert observability.init_sentry() is False


def test_blank_dsn_means_no_sentry(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "   ")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert observability.init_sentry() is False


def test_dsn_without_sdk_installed_does_not_crash(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert observability.init_sentry() is False


@pytest.mark.parametrize("raw,expected", [
    (None, observability.DEFAULT_TRACES_SAMPLE_RATE), ("0.2", 0.2), ("abc", observability.DEFAULT_TRACES_SAMPLE_RATE),
    ("5", 1.0), ("-1", 0.0),
])
def test_traces_sample_rate(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)
    else:
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", raw)
    assert observability._traces_sample_rate() == expected


def test_dsn_configures_sdk_without_pii(monkeypatch):
    sentry_sdk = pytest.importorskip("sentry_sdk")
    captured = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: captured.update(kw))
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

    assert observability.init_sentry() is True
    assert captured["dsn"] == FAKE_DSN
    assert captured["environment"] == "staging"
    assert captured["send_default_pii"] is False
    assert captured["max_request_body_size"] == "never"
    assert captured["include_local_variables"] is False
    assert 0 < captured["traces_sample_rate"] <= 0.1
    names = {type(i).__name__ for i in captured["integrations"]}
    assert {"FastApiIntegration", "StarletteIntegration"} <= names


def test_unhandled_error_reported_end_to_end():
    """Dans un sous-processus (le SDK patche Starlette globalement) : une exception
    non gérée, malgré le handler générique de l'app, remonte à Sentry sans PII."""
    pytest.importorskip("sentry_sdk")
    script = textwrap.dedent(
        """
        import os, sentry_sdk
        from sentry_sdk.transport import Transport
        events = []
        class Capture(Transport):
            def capture_envelope(self, envelope):
                for item in envelope.items:
                    if item.type == "event":
                        events.append(item.payload.json)
        real_init = sentry_sdk.init
        sentry_sdk.init = lambda **kw: real_init(transport=Capture(), **kw)

        from core.observability import init_sentry
        assert init_sentry() is True
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        app = FastAPI()
        @app.exception_handler(Exception)
        async def handler(request: Request, exc: Exception):
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
        @app.post("/boom")
        async def boom():
            raise RuntimeError("kaboom")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/boom", json={"password": "secret-123"},
                        headers={"Authorization": "Bearer tok", "X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 500, r.status_code
        sentry_sdk.flush()
        assert events, "aucun événement capturé"
        ev = events[0]
        assert ev["environment"] == "ci-test"
        assert ev["exception"]["values"][-1]["value"] == "kaboom"
        blob = repr(ev)
        assert "secret-123" not in blob and "Bearer tok" not in blob and "8.8.8.8" not in blob
        print("OK")
        """
    )
    env = dict(os.environ, SENTRY_DSN=FAKE_DSN, ENVIRONMENT="ci-test")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = os.pathsep.join(p for p in (backend_dir, env.get("PYTHONPATH")) if p)
    proc = subprocess.run([sys.executable, "-c", script], cwd=backend_dir, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0 and "OK" in proc.stdout, proc.stdout + proc.stderr
