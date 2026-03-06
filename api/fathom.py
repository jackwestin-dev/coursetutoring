# -*- coding: utf-8 -*-
"""
Fathom API proxy for JW CARS Session Grader.
API key stored securely in FATHOM_API_KEY environment variable on Vercel.

Routes:
  GET  /api/fathom?path=/meetings&limit=100
  GET  /api/fathom?path=/recordings/123/transcript
"""

import os
import json
import ssl
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode

FATHOM_BASE = "https://api.fathom.ai/external/v1"


def make_fathom_request(path, api_key):
    url = f"{FATHOM_BASE}{path}"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            body = r.read().decode("utf-8")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, {"raw": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body or str(e)}
    except Exception as e:
        return 500, {"error": str(e)}


class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status, body):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # API key from Vercel environment variable — never exposed to browser
        api_key = os.environ.get("FATHOM_API_KEY", "").strip()
        if not api_key:
            self._json(500, {"error": "FATHOM_API_KEY environment variable not set"})
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        fathom_path = params.get("path", [None])[0]
        if not fathom_path:
            self._json(400, {"error": "Missing ?path= parameter"})
            return

        # Forward any extra query params (e.g. limit=100)
        extra = {k: v[0] for k, v in params.items() if k != "path"}
        if extra:
            fathom_path = f"{fathom_path}?{urlencode(extra)}"

        status, body = make_fathom_request(fathom_path, api_key)
        self._json(status, body)

    def log_message(self, format, *args):
        pass
