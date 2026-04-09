# -*- coding: utf-8 -*-
"""
Test endpoint: fetch the 3 most recent session records from Supabase and email
them to all directors (one email per recipient). Use to verify everyone receives.
GET /api/send-recent-evaluations
"""

import os
import json
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
FROM_EMAIL = os.environ.get("FROM_EMAIL", "grader@jackwestin.com")
SMTP_USER = os.environ.get("SMTP_USER", "").strip() or FROM_EMAIL
SMTP_PASSWORD = (os.environ.get("SMTP_PASSWORD", "") or "").strip().replace(" ", "")


def get_director_emails():
    """Parse DIRECTOR_EMAILS (comma-separated) or fallback to DIRECTOR_EMAIL. Handles quotes and spaces."""
    def parse(s):
        if not s:
            return []
        s = s.strip().strip('"').strip("'")
        return [e.strip() for e in s.split(",") if e.strip() and "@" in e]

    raw = (os.environ.get("DIRECTOR_EMAILS") or "").strip()
    if raw:
        out = parse(raw)
        if out:
            return out
    single = (os.environ.get("DIRECTOR_EMAIL") or "anastasia@jackwestin.com").strip()
    out = parse(single)
    return out if out else ["anastasia@jackwestin.com"]


def send_email(to_emails, subject, body, html=None):
    if not SMTP_USER or not SMTP_PASSWORD or not to_emails:
        return False, "SMTP or recipients not configured"
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            for recipient in to_emails:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = FROM_EMAIL
                msg["To"] = recipient
                msg.attach(MIMEText(body, "plain", "utf-8"))
                if html:
                    msg.attach(MIMEText(html, "html", "utf-8"))
                server.sendmail(FROM_EMAIL, [recipient], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def fetch_recent(n=3):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None, "Supabase not configured"
    url = f"{SUPABASE_URL}/rest/v1/session_records?order=created_at.desc&select=*"
    req = urllib.request.Request(url, method="GET", headers={
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Range": f"0-{n - 1}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"Supabase {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_email_content(records):
    plain_parts = [
        "JW Session Grader — Test: 3 most recent evaluations",
        "This email was sent to verify that all directors receive mail.",
        "",
        "=" * 60,
        "",
    ]
    html_parts = [
        """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:-apple-system,sans-serif;max-width:680px;margin:0 auto;padding:20px">
        <div style="background:linear-gradient(135deg,#8A5CF6 0%,#B88AFF 100%);color:#fff;padding:20px;border-radius:12px 12px 0 0;text-align:center">
        <strong>JW SESSION GRADER</strong><br>Test: 3 most recent evaluations
        </div>
        <div style="background:#fff;border:1px solid #E5E7EB;padding:20px;margin-bottom:12px">
        <p style="color:#5E6573;font-size:13px">This email was sent to verify that all directors receive mail.</p>
        </div>"""
    ]
    for i, r in enumerate(records, 1):
        tutor = r.get("tutor_name") or "—"
        student = r.get("student_name") or "—"
        date = r.get("session_date") or "—"
        score = r.get("score")
        ct = r.get("course_type", "")
        max_pts = 125 if "cars" in (ct or "").lower() else 135
        score_str = f"{score}/{max_pts}" if score is not None else "—"
        rating = (r.get("rating") or "—").strip()
        report = (r.get("report_text") or "")[:2000]
        plain_parts.append(f"Evaluation #{i}")
        plain_parts.append(f"  Tutor: {tutor} | Student: {student} | Date: {date}")
        plain_parts.append(f"  Score: {score_str} | Rating: {rating}")
        plain_parts.append("")
        plain_parts.append(report[:1500] + ("..." if len(report) > 1500 else ""))
        plain_parts.append("")
        plain_parts.append("-" * 60)
        plain_parts.append("")
        html_parts.append(f"""
        <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;padding:18px;margin-bottom:12px">
        <div style="font-size:11px;font-weight:700;color:#8A5CF6;margin-bottom:8px">EVALUATION #{i}</div>
        <p style="margin:4px 0;font-size:14px;color:#2B2F40"><strong>{esc(tutor)}</strong> · {esc(student)} · {esc(date)}</p>
        <p style="margin:4px 0;font-size:13px">Score: <strong>{score_str}</strong> · {esc(rating)}</p>
        <pre style="background:#fff;border:1px solid #E5E7EB;padding:12px;font-size:12px;overflow-x:auto;white-space:pre-wrap;max-height:200px;overflow-y:auto">{esc((report or "")[:1500])}</pre>
        </div>""")
    html_parts.append('<p style="font-size:11px;color:#9CA3AF;text-align:center">JW Session Grader · Test send</p></body></html>')
    return "\n".join(plain_parts), "".join(html_parts)


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
        try:
            to_emails = get_director_emails()
            if not to_emails:
                self._json(500, {"success": False, "error": "No director emails (DIRECTOR_EMAILS / DIRECTOR_EMAIL)"})
                return
            records, err = fetch_recent(3)
            if err:
                self._json(500, {"success": False, "error": err})
                return
            if not records:
                body = "No session records in Supabase yet. Grade a session in the app to create one."
                html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:20px"><p>{body}</p><p style="color:#9CA3AF;font-size:12px">JW Session Grader · Test send</p></body></html>"""
                subject = "JW Session Grader — Test (no records yet)"
                ok, send_err = send_email(to_emails, subject, body, html=html)
                self._json(200, {"success": ok, "sent": ok, "to": to_emails, "records_count": 0, "error": send_err})
                return
            body, html = build_email_content(records)
            subject = f"JW Session Grader — Test: {len(records)} recent evaluation(s)"
            ok, send_err = send_email(to_emails, subject, body, html=html)
            if ok:
                self._json(200, {"success": True, "sent": True, "to": to_emails, "records_count": len(records)})
            else:
                self._json(500, {"success": False, "error": send_err, "to": to_emails, "records_count": len(records)})
        except Exception as e:
            self._json(500, {"success": False, "error": str(e)})

    def log_message(self, format, *args):
        pass
