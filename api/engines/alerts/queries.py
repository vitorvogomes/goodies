"""SQL da engine `alerts`: dona só de `alert_dismissals` (AD-3)."""

from __future__ import annotations

DISMISSED = "SELECT key, fingerprint FROM alert_dismissals"
FORGET_GONE = "DELETE FROM alert_dismissals WHERE key <> ALL($1::text[])"
DISMISS = """
    INSERT INTO alert_dismissals (key, fingerprint) VALUES ($1, $2)
    ON CONFLICT (key) DO UPDATE SET fingerprint = EXCLUDED.fingerprint, dismissed_at = now()
"""
DATA_UNTIL = "SELECT max(date) FROM transactions"
