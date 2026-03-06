# -*- coding: utf-8 -*-
"""
Send email (e.g. management report to directors).
POST body: { "subject": "...", "body": "..." }
Sends to DIRECTOR_EMAILS (comma-separated env var).
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import BaseHTTPRequestHandler

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "grader@jackwestin.com")


def get_director_emails():
    raw = os.environ.get("DIRECTOR_EMAILS", "")
    if not raw:
        # Fallback: single director
        single = os.environ.get("DIRECTOR_EMAIL", "anastasia@jackwestin.com")
        return [e.strip() for e in single.split(",") if e.strip()]
    return [e.strip() for e in raw.split(",") if e.strip()]


def send_email(to_emails, subject, body):
    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "SMTP not configured"
    if not to_emails:
        return False, "No recipients"
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


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
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

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if not content_length:
            self._json(400, {"success": False, "error": "Missing body"})
            return
        try:
            raw = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"success": False, "error": "Invalid JSON"})
            return
        subject = data.get("subject", "").strip()
        body = data.get("body", "").strip()
        if not subject or not body:
            self._json(400, {"success": False, "error": "subject and body required"})
            return
        to_emails = get_director_emails()
        ok, err = send_email(to_emails, subject, body)
        if ok:
            self._json(200, {"success": True, "sent_to": to_emails})
        else:
            self._json(500, {"success": False, "error": err or "Send failed"})

    def log_message(self, format, *args):
        pass
