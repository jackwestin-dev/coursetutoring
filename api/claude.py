# -*- coding: utf-8 -*-
"""
Claude API proxy for JW CARS Session Grader.
API key stored in ANTHROPIC_API_KEY on Vercel — never exposed to browser.
POST body: { "system": "...", "messages": [{ "role": "user", "content": "..." }] }
"""

import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def read_body(handler):
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length:
        return handler.rfile.read(content_length).decode("utf-8")
    return "{}"


class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, status, body):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if not ANTHROPIC_API_KEY:
            self._json_response(500, {"error": "ANTHROPIC_API_KEY environment variable not set"})
            return

        try:
            raw = read_body(self)
            data = json.loads(raw)
            system = data.get("system", "")
            messages = data.get("messages", [])
            if not messages:
                self._json_response(400, {"error": "messages required"})
                return
        except json.JSONDecodeError as e:
            self._json_response(400, {"error": f"Invalid JSON: {e}"})
            return

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
            "system": system,
            "messages": messages,
        }

        req = urllib.request.Request(
            ANTHROPIC_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read().decode())
                text = "".join(
                    b.get("text", "")
                    for b in out.get("content", [])
                    if b.get("type") == "text"
                )
                self._json_response(200, {"content": text})
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else str(e)
            try:
                err = json.loads(body)
                msg = err.get("error", {}).get("message", body)
            except Exception:
                msg = body
            self._json_response(e.code, {"error": msg})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def log_message(self, format, *args):
        pass
