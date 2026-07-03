"""ADR-040 — Callback writer for async backtest jobs.

The engine cannot reach Supabase directly (Lovable Cloud hides the service_role key), so it
POSTs updates to the `backtest-callback` edge function, which writes the row server-side.
Auth is a shared secret sent in the X-Callback-Secret header. The callback URL and secret
arrive per-request (from run-backtest) — never stored in code, never logged.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import requests


def _allowed_host_suffix() -> str:
    # Default to Supabase's functions domain; overridable for self-hosting/tests.
    return os.environ.get("CALLBACK_ALLOWED_HOST_SUFFIX", ".supabase.co")


def is_allowed_callback_url(url: str) -> bool:
    """True only for https URLs whose host is under the allowed suffix (SSRF guard).

    Uses the parsed hostname (so `https://ok.supabase.co@evil.com` is rejected — its
    hostname is evil.com). Blocks metadata/private/loopback/external hosts wholesale.
    """
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https" or not p.hostname:
        return False
    host = p.hostname.lower()
    suffix = _allowed_host_suffix().lower()
    return host == suffix.lstrip(".") or host.endswith(suffix)


class CallbackWriter:
    """POST {run_id, fields} to the backtest-callback edge function."""

    def __init__(self, url: str, secret: str, timeout: float = 15.0):
        self.url = url
        self._secret = secret
        self.timeout = timeout

    def update_run(self, run_id: str, fields: dict) -> None:
        """POST an update for one run. Raises on non-2xx."""
        resp = requests.post(
            self.url,
            json={"run_id": run_id, "fields": fields},
            headers={
                "Content-Type": "application/json",
                "X-Callback-Secret": self._secret,
            },
            timeout=self.timeout,
            allow_redirects=False,  # a redirect must never bounce the secret to another host
        )
        resp.raise_for_status()


def get_callback_writer(callback_url: Optional[str],
                        callback_secret: Optional[str]) -> Optional[CallbackWriter]:
    """Build a writer, or None if either value is missing. The endpoint enforces the
    host allowlist (is_allowed_callback_url) before this is called."""
    if not callback_url or not callback_secret:
        return None
    return CallbackWriter(callback_url, callback_secret)
