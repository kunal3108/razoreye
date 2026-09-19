from __future__ import annotations

import difflib
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("RAZOREYE_DB", BASE_DIR / "razoreye.db"))
USER_AGENT = "Razoreye/1.0 llms.txt monitor"
DEMOPAY_URL = "demo://demopay/llms.txt"
DEMOPAY_SOURCE = BASE_DIR / "demo_sources" / "demopay-llms.txt"
DEMOPAY_VERSION_1 = """# DemoPay

## Products
- Payment Gateway
- Payment Links

## APIs
- Payments API
- Refund API
- Webhooks
"""
DEMOPAY_VERSION_2 = """# DemoPay

## Products
- Payment Gateway
- Payment Links
- International Payments
- Subscriptions

## APIs
- Payments API
- Refund API
- Webhooks
- International Payments API
- Subscription API
- MCP Server
"""

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "razoreye-development-key")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                check_interval INTEGER NOT NULL DEFAULT 60,
                active INTEGER NOT NULL DEFAULT 1,
                last_checked_at TEXT,
                last_changed_at TEXT,
                last_status INTEGER,
                last_error TEXT,
                current_hash TEXT,
                current_content TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id INTEGER NOT NULL,
                detected_at TEXT NOT NULL,
                old_content TEXT NOT NULL,
                new_content TEXT NOT NULL,
                diff_text TEXT NOT NULL,
                FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_changes_competitor
            ON changes(competitor_id, detected_at DESC);
            """
        )


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("Enter a valid website or llms.txt URL.")
    if parsed.path in ("", "/"):
        return value.rstrip("/") + "/llms.txt"
    return value


def make_diff(old: str, new: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )


def check_competitor(competitor_id: int) -> tuple[bool, str]:
    with get_db() as db:
        competitor = db.execute(
            "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()
        if not competitor:
            return False, "Competitor not found."

    checked_at = utc_now()
    try:
        if competitor["url"] == DEMOPAY_URL:
            content = DEMOPAY_SOURCE.read_text(encoding="utf-8")
            status_code = 200
        else:
            response = requests.get(
                competitor["url"],
                headers={"User-Agent": USER_AGENT, "Accept": "text/plain,*/*"},
                timeout=15,
                allow_redirects=True,
            )
            response.raise_for_status()
            content = response.text
            status_code = response.status_code
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        changed = bool(
            competitor["current_hash"] and competitor["current_hash"] != content_hash
        )

        with get_db() as db:
            if changed:
                db.execute(
                    """
                    INSERT INTO changes
                    (competitor_id, detected_at, old_content, new_content, diff_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        competitor_id,
                        checked_at,
                        competitor["current_content"] or "",
                        content,
                        make_diff(competitor["current_content"] or "", content),
                    ),
                )
            db.execute(
                """
                UPDATE competitors
                SET last_checked_at = ?, last_changed_at = CASE WHEN ? THEN ? ELSE last_changed_at END,
                    last_status = ?, last_error = NULL, current_hash = ?, current_content = ?
                WHERE id = ?
                """,
                (
                    checked_at,
                    int(changed),
                    checked_at,
                    status_code,
                    content_hash,
                    content,
                    competitor_id,
                ),
            )
        return changed, "Change detected." if changed else "No changes detected."
    except requests.RequestException as exc:
        with get_db() as db:
            db.execute(
                """
                UPDATE competitors
                SET last_checked_at = ?, last_status = NULL, last_error = ?
                WHERE id = ?
                """,
                (checked_at, str(exc)[:500], competitor_id),
            )
        return False, f"Check failed: {exc}"


def ensure_demopay_monitor() -> None:
    DEMOPAY_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not DEMOPAY_SOURCE.exists():
        DEMOPAY_SOURCE.write_text(DEMOPAY_VERSION_1, encoding="utf-8")
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM competitors WHERE url = ?", (DEMOPAY_URL,)
        ).fetchone()
        if not existing:
            cursor = db.execute(
                """
                INSERT INTO competitors
                (name, url, check_interval, active, created_at)
                VALUES ('DemoPay', ?, 60, 1, ?)
                """,
                (DEMOPAY_URL, utc_now()),
            )
            competitor_id = cursor.lastrowid
        else:
            competitor_id = existing["id"]
    with get_db() as db:
        baseline_exists = db.execute(
            "SELECT current_hash FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()["current_hash"]
    if not baseline_exists:
        check_competitor(competitor_id)


def run_scheduled_checks() -> None:
    now = datetime.now(timezone.utc)
    with get_db() as db:
        competitors = db.execute(
            "SELECT id, check_interval, last_checked_at FROM competitors WHERE active = 1"
        ).fetchall()
    for competitor in competitors:
        last_checked = competitor["last_checked_at"]
        due = not last_checked
        if last_checked:
            elapsed = (now - datetime.fromisoformat(last_checked)).total_seconds() / 60
            due = elapsed >= competitor["check_interval"]
        if due:
            check_competitor(competitor["id"])


@app.template_filter("domain")
def domain_filter(value: str) -> str:
    return urlparse(value).netloc.removeprefix("www.")


@app.template_filter("short_time")
def short_time_filter(value: str | None) -> str:
    if not value:
        return "Never"
    return datetime.fromisoformat(value).strftime("%b %d, %H:%M UTC")


@app.get("/")
def dashboard():
    with get_db() as db:
        competitors = db.execute(
            """
            SELECT c.*, COUNT(ch.id) AS change_count
            FROM competitors c
            LEFT JOIN changes ch ON ch.competitor_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
        recent_changes = db.execute(
            """
            SELECT ch.*, c.name AS competitor_name
            FROM changes ch
            JOIN competitors c ON c.id = ch.competitor_id
            ORDER BY ch.detected_at DESC LIMIT 6
            """
        ).fetchall()
    total_changes = sum(item["change_count"] for item in competitors)
    healthy = sum(
        1 for item in competitors if item["last_status"] and not item["last_error"]
    )
    return render_template(
        "dashboard.html",
        competitors=competitors,
        recent_changes=recent_changes,
        total_changes=total_changes,
        healthy=healthy,
    )


@app.post("/competitors")
def add_competitor():
    name = request.form.get("name", "").strip()
    try:
        url = normalize_url(request.form.get("url", ""))
        interval = max(5, int(request.form.get("check_interval", "60")))
        if not name:
            raise ValueError("Competitor name is required.")
        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO competitors (name, url, check_interval, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, url, interval, utc_now()),
            )
        check_competitor(cursor.lastrowid)
        flash(f"{name} is now being monitored.", "success")
    except (ValueError, sqlite3.IntegrityError) as exc:
        message = (
            "That llms.txt URL is already being monitored."
            if isinstance(exc, sqlite3.IntegrityError)
            else str(exc)
        )
        flash(message, "error")
    return redirect(url_for("dashboard"))


@app.get("/competitors/<int:competitor_id>")
def competitor_detail(competitor_id: int):
    with get_db() as db:
        competitor = db.execute(
            "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()
        changes = db.execute(
            "SELECT * FROM changes WHERE competitor_id = ? ORDER BY detected_at DESC",
            (competitor_id,),
        ).fetchall()
    if not competitor:
        return render_template("404.html"), 404
    return render_template(
        "competitor.html", competitor=competitor, changes=changes
    )


@app.get("/demo/demopay/llms.txt")
def demopay_llms_txt():
    return DEMOPAY_SOURCE.read_text(encoding="utf-8"), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


@app.post("/competitors/<int:competitor_id>/simulate")
def simulate_demopay_change(competitor_id: int):
    with get_db() as db:
        competitor = db.execute(
            "SELECT url FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()
    if not competitor or competitor["url"] != DEMOPAY_URL:
        return render_template("404.html"), 404
    DEMOPAY_SOURCE.write_text(DEMOPAY_VERSION_2, encoding="utf-8")
    changed, message = check_competitor(competitor_id)
    flash(
        "DemoPay Version 2 detected and saved."
        if changed
        else "DemoPay is already on Version 2.",
        "change" if changed else "success",
    )
    return redirect(request.referrer or url_for("competitor_detail", competitor_id=competitor_id))


@app.post("/competitors/<int:competitor_id>/reset-demo")
def reset_demopay(competitor_id: int):
    with get_db() as db:
        competitor = db.execute(
            "SELECT url FROM competitors WHERE id = ?", (competitor_id,)
        ).fetchone()
    if not competitor or competitor["url"] != DEMOPAY_URL:
        return render_template("404.html"), 404
    DEMOPAY_SOURCE.write_text(DEMOPAY_VERSION_1, encoding="utf-8")
    baseline_hash = hashlib.sha256(DEMOPAY_VERSION_1.encode("utf-8")).hexdigest()
    with get_db() as db:
        db.execute("DELETE FROM changes WHERE competitor_id = ?", (competitor_id,))
        db.execute(
            """
            UPDATE competitors
            SET current_hash = ?, current_content = ?, last_status = 200,
                last_error = NULL, last_checked_at = ?, last_changed_at = NULL
            WHERE id = ?
            """,
            (baseline_hash, DEMOPAY_VERSION_1, utc_now(), competitor_id),
        )
    flash("DemoPay reset to the Version 1 baseline.", "success")
    return redirect(request.referrer or url_for("competitor_detail", competitor_id=competitor_id))


@app.post("/competitors/<int:competitor_id>/check")
def manual_check(competitor_id: int):
    changed, message = check_competitor(competitor_id)
    flash(message, "change" if changed else "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.post("/competitors/<int:competitor_id>/toggle")
def toggle_competitor(competitor_id: int):
    with get_db() as db:
        db.execute(
            "UPDATE competitors SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
            (competitor_id,),
        )
    return redirect(request.referrer or url_for("dashboard"))


@app.post("/competitors/<int:competitor_id>/delete")
def delete_competitor(competitor_id: int):
    with get_db() as db:
        db.execute("DELETE FROM competitors WHERE id = ?", (competitor_id,))
    flash("Monitor deleted.", "success")
    return redirect(url_for("dashboard"))


@app.get("/healthz")
def health():
    return jsonify({"status": "ok", "service": "razoreye"})


init_db()
ensure_demopay_monitor()
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_scheduled_checks, "interval", minutes=1, max_instances=1)
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    scheduler.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))