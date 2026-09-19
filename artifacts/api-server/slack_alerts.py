from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


logger = logging.getLogger(__name__)

SLACK_CHANNEL_ID = os.environ.get("RAZOREYE_SLACK_CHANNEL", "C0C33L7GE3T")
SLACK_CONTACT_ID = os.environ.get("RAZOREYE_SLACK_CONTACT", "U0C2LB48WPR")
SLACK_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _slack_request(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    identity = os.environ.get("REPL_IDENTITY")
    renewal = os.environ.get("WEB_REPL_RENEWAL")
    token = f"repl {identity}" if identity else f"depl {renewal}" if renewal else None
    if not hostname or not token:
        raise RuntimeError("Replit connector runtime is unavailable")

    response = requests.post(
        f"https://{hostname}/api/v2/proxy/{method}",
        headers={
            "Content-Type": "application/json",
            "X-Replit-Token": token,
            "Connector-Name": "slack",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Slack {method} failed: {body.get('error', 'unknown_error')}")
    return body


def _post_message(text: str, thread_ts: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"channel": SLACK_CHANNEL_ID, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return _slack_request("chat.postMessage", payload)


def _analysis_reply(competitor_name: str, analysis: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"<@{SLACK_CONTACT_ID}> *RAZOREYE ANALYSIS — {competitor_name}*",
            f"*Signal:* {analysis.get('signal', 'Not available')}",
            f"*Impact:* {analysis.get('impact', 'Not available')}",
            f"*Your coverage:* {analysis.get('coverage', 'Not available')}",
            f"*Recommendation:* {analysis.get('recommendation', 'Not available')}",
            f"*Next step:* {analysis.get('next_step', 'Not available')}",
        )
    )


def send_daily_slack_alert(database_path: Path) -> bool:
    """Post one daily summary and thread each detected change beneath it."""
    now_utc = datetime.now(timezone.utc)
    local_day = now_utc.astimezone(SLACK_TIMEZONE).date().isoformat()
    cutoff = (now_utc - timedelta(hours=24)).isoformat(timespec="seconds")

    with sqlite3.connect(database_path) as db:
        db.row_factory = sqlite3.Row
        already_sent = db.execute(
            "SELECT 1 FROM slack_alert_runs WHERE report_date = ? AND status = 'sent'",
            (local_day,),
        ).fetchone()
        if already_sent:
            return False
        rows = db.execute(
            """
            SELECT ch.id, ch.detected_at, ch.analysis_json, c.name AS competitor_name
            FROM changes ch
            JOIN competitors c ON c.id = ch.competitor_id
            WHERE ch.detected_at >= ?
            ORDER BY ch.detected_at ASC
            """,
            (cutoff,),
        ).fetchall()

    date_label = now_utc.astimezone(SLACK_TIMEZONE).strftime("%d %b %Y")
    if not rows:
        parent_text = (
            f"*Razoreye daily alert — {date_label}*\n"
            "No changes in llms.txt for monitored competitors in the last 24 hours."
        )
    else:
        competitor_count = len({row["competitor_name"] for row in rows})
        parent_text = (
            f"*Razoreye daily alert — {date_label}*\n"
            f"Changes detected: {len(rows)} across {competitor_count} "
            f"{'competitor' if competitor_count == 1 else 'competitors'}."
        )

    try:
        parent = _post_message(parent_text)
        parent_ts = parent["ts"]
        for row in rows:
            analysis = (
                json.loads(row["analysis_json"]) if row["analysis_json"] else {}
            )
            _post_message(
                _analysis_reply(row["competitor_name"], analysis),
                thread_ts=parent_ts,
            )
        with sqlite3.connect(database_path) as db:
            db.execute(
                """
                INSERT INTO slack_alert_runs
                    (report_date, sent_at, status, parent_ts, error)
                VALUES (?, ?, 'sent', ?, NULL)
                ON CONFLICT(report_date) DO UPDATE SET
                    sent_at = excluded.sent_at,
                    status = excluded.status,
                    parent_ts = excluded.parent_ts,
                    error = NULL
                """,
                (local_day, now_utc.isoformat(timespec="seconds"), parent_ts),
            )
        return True
    except Exception as exc:
        logger.exception("Daily Slack alert failed")
        with sqlite3.connect(database_path) as db:
            db.execute(
                """
                INSERT INTO slack_alert_runs
                    (report_date, sent_at, status, parent_ts, error)
                VALUES (?, ?, 'failed', NULL, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    sent_at = excluded.sent_at,
                    status = excluded.status,
                    parent_ts = NULL,
                    error = excluded.error
                """,
                (
                    local_day,
                    now_utc.isoformat(timespec="seconds"),
                    str(exc)[:500],
                ),
            )
        return False