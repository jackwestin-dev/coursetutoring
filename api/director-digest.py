# -*- coding: utf-8 -*-
"""
Director digest: runs daily (Vercel Cron), fetches session records from Supabase,
emails directors with (1) tutors needing intervention first, (2) progress summary.
GET /api/director-digest (called by cron or manually).
"""

import os
import json
import smtplib
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
FROM_EMAIL = os.environ.get("FROM_EMAIL", "grader@jackwestin.com")
SMTP_USER = os.environ.get("SMTP_USER", "").strip() or FROM_EMAIL
SMTP_PASSWORD = (os.environ.get("SMTP_PASSWORD", "") or "").strip().replace(" ", "")

# Score/rating thresholds: below Meets = needs attention (see docs/SCORE_BANDS_AND_INTERVENTION.md)
INTERVENTION_SCORE_THRESHOLD = 75  # below this = flag
INTERVENTION_RATINGS = ("Needs Remediation", "Needs Minor Calibration")


def get_director_emails():
    raw = os.environ.get("DIRECTOR_EMAILS", "")
    if not raw:
        single = os.environ.get("DIRECTOR_EMAIL", "anastasia@jackwestin.com")
        return [e.strip() for e in single.split(",") if e.strip()]
    return [e.strip() for e in raw.split(",") if e.strip()]


def send_email(to_emails, subject, body):
    if not SMTP_USER or not SMTP_PASSWORD or not to_emails:
        return False, "SMTP or recipients not configured"
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = ", ".join(to_emails)
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_emails, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def fetch_sessions_last_n_days(days=1):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None, "Supabase not configured"
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{SUPABASE_URL}/rest/v1/session_records?created_at=gte.{since}&order=created_at.desc&select=*"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"Supabase {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)


def build_intervention_list(sessions):
    """Tutors not abiding by SOPs: score < 75 or rating is Needs Remediation / Needs Minor Calibration."""
    seen = set()
    out = []
    for s in sessions:
        name = (s.get("tutor_name") or "Unknown").strip()
        if not name:
            continue
        score = s.get("score")
        rating = (s.get("rating") or "").strip()
        needs_intervention = False
        if score is not None and score < INTERVENTION_SCORE_THRESHOLD:
            needs_intervention = True
        if rating in INTERVENTION_RATINGS:
            needs_intervention = True
        if not needs_intervention:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        score_str = f"Score {score}/100" if score is not None else "No score"
        out.append(f"  • {name} — {score_str} | {rating or 'N/A'}")
    return out


def summarize_with_claude(sessions, intervention_names):
    if not ANTHROPIC_API_KEY or not sessions:
        return None, "Claude not configured or no sessions"
    system = """You are a concise analyst for Jack Westin's MCAT tutoring program. Given session records (tutor, student, date, score, rating) and a list of tutors already flagged for intervention, write a SHORT "Progress & notes" section (2–3 paragraphs) that:
1. Summarizes volume and which tutors had sessions.
2. Highlights any positives or improvements.
3. Adds 1–2 actionable bullets only if relevant.
Use plain text, no markdown. Be brief."""
    rows_text = []
    for s in sessions[:40]:
        rows_text.append(
            f"- {s.get('tutor_name')} | {s.get('student_name')} | {s.get('session_date')} | Session {s.get('session_number')} | Score {s.get('score')}/100 | {s.get('rating')}"
        )
    user_content = (
        "Tutors already flagged for intervention (list first in email): "
        + ", ".join(intervention_names[:30])
        + "\n\nSession records (last 24h):\n\n"
        + "\n".join(rows_text)
    )
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1200,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read().decode())
            text = "".join(
                b.get("text", "") for b in out.get("content", []) if b.get("type") == "text"
            )
            return text.strip(), None
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else str(e)
        return None, body[:300]
    except Exception as e:
        return None, str(e)


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status, data):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # Daily digest: last 1 day of sessions
        sessions, fetch_err = fetch_sessions_last_n_days(days=1)
        if fetch_err:
            self._json(500, {"success": False, "error": fetch_err})
            return

        to_emails = get_director_emails()
        if not to_emails:
            self._json(500, {"success": False, "error": "No director emails configured"})
            return

        # Build intervention list first (tutors not abiding by SOPs)
        intervention_lines = build_intervention_list(sessions) if sessions else []
        intervention_names = []
        for line in intervention_lines:
            # "  • Name — Score ..." -> Name
            part = line.strip().lstrip("•").strip()
            if " — " in part:
                intervention_names.append(part.split(" — ")[0].strip())

        if not sessions:
            body = "No sessions graded in the last 24 hours. Transcripts can be entered manually in the Session Grader app (paste transcript + student notes, then Grade)."
            subject = "JW Daily Tutor Digest — No sessions in last 24h"
        else:
            # Email body: intervention list first, then progress
            parts = [
                "TUTORS NEEDING INTERVENTION (not abiding by SOPs)",
                "See docs/SCORE_BANDS_AND_INTERVENTION.md for band definitions.",
                "",
            ]
            if intervention_lines:
                parts.extend(intervention_lines)
                parts.append("")
            else:
                parts.append("  (None in this period)")
                parts.append("")

            parts.append("---")
            parts.append("")
            parts.append("PROGRESS & NOTES")
            parts.append("")

            progress, claude_err = summarize_with_claude(sessions, intervention_names)
            if claude_err:
                progress = f"Session count: {len(sessions)}. Summary unavailable: {claude_err}"
            parts.append(progress or "No summary.")

            body = "\n".join(parts)
            n_intervention = len(intervention_lines)
            subject = f"JW Daily Tutor Digest — {len(sessions)} session(s) | {n_intervention} tutor(s) needing intervention"

        ok, send_err = send_email(to_emails, subject, body)
        if ok:
            self._json(200, {
                "success": True,
                "sessions": len(sessions) if sessions else 0,
                "intervention_count": len(intervention_lines),
                "sent": True,
                "to": to_emails,
            })
        else:
            self._json(500, {"success": False, "error": send_err, "sessions": len(sessions) if sessions else 0})

    def log_message(self, format, *args):
        pass
