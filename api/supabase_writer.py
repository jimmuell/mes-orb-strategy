"""ADR-037 — Supabase writer for async backtest jobs.

Updates a `backtest_runs` row by id via the Supabase REST (PostgREST) API using the
service-role key (trusted server-side; bypasses RLS). Auth comes ONLY from the env vars
SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY — no secrets in code. `get_supabase_writer()`
returns None when unset so the caller can fail loudly (503) instead of silently.

Kept deliberately small and dependency-light (uses `requests`, already a runtime dep) and
injectable, so the async flow is unit-tested with a fake writer — no live Supabase needed.
"""
from __future__ import annotations

import os
from typing import Optional

import requests


class SupabaseWriter:
    """Minimal PostgREST client scoped to updating one table's rows by id."""

    def __init__(self, url: str, service_role_key: str,
                 table: str = "backtest_runs", timeout: float = 15.0):
        self.base = url.rstrip("/")
        self._key = service_role_key
        self.table = table
        self.timeout = timeout

    def update_run(self, run_id: str, fields: dict) -> None:
        """PATCH backtest_runs where id == run_id. Raises on non-2xx."""
        endpoint = f"{self.base}/rest/v1/{self.table}"
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        resp = requests.patch(
            endpoint,
            params={"id": f"eq.{run_id}"},
            json=fields,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()


def get_supabase_writer() -> Optional[SupabaseWriter]:
    """Build a writer from env, or None if SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return SupabaseWriter(url, key)
