"""In-process WIT run store (WIT-P3d).

A dict + threading.Lock keyed by run_id, plus an idempotency index keyed
(evaluation_id, config_hash) -> run_id. Resubmitting the same evaluation + config
returns the EXISTING run (WIT-03 §3.1), so a double-submit never launches a second
job.

RESTART-LOSSY, on purpose (v1): this store lives in the process. A Railway restart
or redeploy loses all run state — in-flight runs are dropped and their run_ids
become unknown (GET -> 404). The poll-fallback + the caller's own record
(Supabase `runs` row, WIT-03 §6) cover this; the callback is best-effort. A durable
store (Redis/Postgres) is a later slice. Documented here so nobody assumes
persistence.
"""
from __future__ import annotations

import threading
import uuid


class WITRunStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}
        self._idempotency: dict[tuple[str, str], str] = {}

    def register(self, evaluation_id: str, config_hash: str, initial: dict) -> tuple[str, bool]:
        """Atomically get-or-create a run for (evaluation_id, config_hash).

        Returns (run_id, is_new). If is_new is False the caller must NOT launch a
        job — the existing run already owns it (idempotency).
        """
        key = (evaluation_id, config_hash)
        with self._lock:
            existing = self._idempotency.get(key)
            if existing is not None:
                return existing, False
            run_id = "wr_" + uuid.uuid4().hex
            state = {"run_id": run_id, "evaluation_id": evaluation_id,
                     "config_hash": config_hash, **initial}
            self._runs[run_id] = state
            self._idempotency[key] = run_id
            return run_id, True

    def get(self, run_id: str) -> dict | None:
        with self._lock:
            s = self._runs.get(run_id)
            return dict(s) if s is not None else None

    def update(self, run_id: str, fields: dict) -> None:
        with self._lock:
            s = self._runs.get(run_id)
            if s is not None:
                s.update(fields)
