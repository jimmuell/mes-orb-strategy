"""ADR-040 — Callback writer for async backtest jobs.

The engine cannot reach Supabase directly (Lovable Cloud hides the service_role key), so it
POSTs updates to the `backtest-callback` edge function, which writes the row server-side.
Auth is a shared secret sent in the X-Callback-Secret header. The callback URL and secret
arrive per-request (from run-backtest) — never stored in code, never logged.
"""
from __future__ import annotations

from typing import Optional

import requests


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
        )
        resp.raise_for_status()


def get_callback_writer(callback_url: Optional[str],
                        callback_secret: Optional[str]) -> Optional[CallbackWriter]:
    """Build a writer, or None if either value is missing."""
    if not callback_url or not callback_secret:
        return None
    return CallbackWriter(callback_url, callback_secret)
