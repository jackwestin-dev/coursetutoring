# -*- coding: utf-8 -*-
"""
Director digest: runs every 3 days (Vercel Cron), fetches session records from
Supabase, uses Claude to summarize tutor progress and improvements, emails directors.
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
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")


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


def fetch_sessions_last_3_days():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None, "Supabase not configured"
    since = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
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


def summarize_with_claude(sessions):
    if not ANTHROPIC_API_KEY or not sessions:
        return None, "Claude not configured or no sessions"
    system = """You are a concise analyst for Jack Westin's MCAT tutoring program. Given a list of graded session records (tutor, student, date, score, rating, and report excerpts), write a short director digest (2–4 paragraphs) that:
1. Summarizes volume and which tutors had sessions.
2. Highlights tutor progress and strengths.
3. Notes any recurring issues or areas for improvement.
4. Ends with 2–3 actionable bullets if relevant.
Keep the tone professional and scannable. Use plain text, no markdown."""
    rows_text = []
    for s in sessions[:50]:  # cap for token limit
        rows_text.append(
            f"- {s.get('tutor_name')} | {s.get('student_name')} | {s.get('session_date')} | Session {s.get('session_number')} | {s.get('course_type')} | Score {s.get('score')}/100 | {s.get('rating')}\n  Report excerpt: {(s.get('report_text') or '')[:800]}"
        )
    user_content = "Session records (last 3 days):\n\n" + "\n\n".join(rows_text)
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
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
        sessions, fetch_err = fetch_sessions_last_3_days()
        if fetch_err:
            self._json(500, {"success": False, "error": fetch_err})
            return
        if not sessions:
            self._json(200, {"success": True, "message": "No sessions in last 3 days", "sent": False})
            return
        digest, claude_err = summarize_with_claude(sessions)
        if claude_err:
            digest = f"Session count (last 3 days): {len(sessions)}. Could not generate AI summary: {claude_err}\n\nRaw list:\n" + "\n".join(
                f"- {s.get('tutor_name')} | {s.get('student_name')} | {s.get('session_date')} | Score {s.get('score')}"
                for s in sessions[:30]
            )
        subject = f"JW Tutor Progress Digest — {len(sessions)} session(s) in last 3 days"
        to_emails = get_director_emails()
        ok, send_err = send_email(to_emails, subject, digest or "No content.")
        if ok:
            self._json(200, {"success": True, "sessions": len(sessions), "sent": True, "to": to_emails})
        else:
            self._json(500, {"success": False, "error": send_err, "sessions": len(sessions)})

    def log_message(self, format, *args):
        pass
