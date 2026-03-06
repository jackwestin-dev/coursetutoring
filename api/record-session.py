# -*- coding: utf-8 -*-
"""
Record a graded session (transcript + host data + grading outcome) to Supabase.
Used so we can run a 3-day director digest of tutor progress.
POST body: tutor_name, tutor_email, student_name, session_date, session_number,
           course_type, score, rating, report_text, transcript_text, host_data?, fathom_notes?
"""

import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def insert_session(data):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False, "Supabase not configured (SUPABASE_URL, SUPABASE_SERVICE_KEY)"
    url = f"{SUPABASE_URL}/rest/v1/session_records"
    payload = {
        "tutor_name": data.get("tutor_name"),
        "tutor_email": data.get("tutor_email"),
        "student_name": data.get("student_name"),
        "session_date": data.get("session_date"),
        "session_number": data.get("session_number"),
        "course_type": data.get("course_type"),
        "score": data.get("score"),
        "rating": data.get("rating"),
        "report_text": data.get("report_text"),
        "transcript_text": data.get("transcript_text"),
        "host_data": data.get("host_data"),
        "fathom_notes": data.get("fathom_notes"),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, None
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return False, f"Supabase {e.code}: {err_body[:200]}"
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
        ok, err = insert_session(data)
        if ok:
            self._json(200, {"success": True})
        else:
            self._json(500, {"success": False, "error": err})

    def log_message(self, format, *args):
        pass
