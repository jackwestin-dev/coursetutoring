# -*- coding: utf-8 -*-
"""
Director digest: runs every 3 days (Vercel Cron), fetches session records from
Supabase, builds a visual HTML email with intervention alerts, score distribution,
tutor trends, and AI narrative. Emails directors.
GET /api/director-digest (called by cron or manually).
"""

import os
import json
import smtplib
import urllib.request
import urllib.error
import math
from collections import defaultdict
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

INTERVENTION_SCORE_THRESHOLD = 75
INTERVENTION_RATINGS = ("Needs Remediation", "Needs Minor Calibration")
DIGEST_DAYS = 3


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


def fetch_sessions(days):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None, "Supabase not configured"
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{SUPABASE_URL}/rest/v1/session_records?created_at=gte.{since}&order=created_at.desc&select=*"
    req = urllib.request.Request(url, method="GET", headers={
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"Supabase {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)


def fetch_all_sessions_for_tutor_history():
    """Fetch last 30 days for trend data."""
    return fetch_sessions(days=30)


def analyze_sessions(sessions):
    """Build analytics from session list."""
    tutor_data = defaultdict(lambda: {"scores": [], "sessions": [], "ratings": []})
    band_counts = {"exceeds": 0, "meets": 0, "calibration": 0, "remediation": 0}

    for s in sessions:
        name = (s.get("tutor_name") or "Unknown").strip()
        score = s.get("score")
        rating = (s.get("rating") or "").strip()
        tutor_data[name]["scores"].append(score)
        tutor_data[name]["sessions"].append(s)
        tutor_data[name]["ratings"].append(rating)
        if score is not None:
            if score >= 90: band_counts["exceeds"] += 1
            elif score >= 75: band_counts["meets"] += 1
            elif score >= 60: band_counts["calibration"] += 1
            else: band_counts["remediation"] += 1

    intervention = []
    performing = []
    for name, data in sorted(tutor_data.items()):
        valid = [s for s in data["scores"] if s is not None]
        avg = sum(valid) / len(valid) if valid else 0
        worst = min(valid) if valid else 0
        best = max(valid) if valid else 0
        needs_flag = worst < INTERVENTION_SCORE_THRESHOLD or any(r in INTERVENTION_RATINGS for r in data["ratings"])
        entry = {"name": name, "avg": round(avg), "worst": worst, "best": best, "count": len(data["sessions"]), "scores": valid, "ratings": data["ratings"]}
        if needs_flag:
            intervention.append(entry)
        else:
            performing.append(entry)

    intervention.sort(key=lambda x: x["worst"])
    performing.sort(key=lambda x: -x["avg"])

    return tutor_data, band_counts, intervention, performing


def build_score_bar_svg(score, max_w=200):
    if score is None:
        return ""
    pct = min(100, max(0, score))
    w = int(pct / 100 * max_w)
    color = "#dc2626" if pct < 60 else "#d97706" if pct < 75 else "#8A5CF6" if pct < 90 else "#16a34a"
    return f'<div style="display:inline-block;width:{max_w}px;height:14px;background:#f3f4f6;border-radius:7px;vertical-align:middle;margin-right:8px"><div style="width:{w}px;height:14px;background:{color};border-radius:7px"></div></div>'


def build_trend_sparkline(scores, width=120, height=32):
    """Build an inline SVG sparkline for score trend."""
    if len(scores) < 2:
        return ""
    n = len(scores)
    x_step = width / max(n - 1, 1)
    y_min, y_max = 0, 100
    points = []
    for i, s in enumerate(scores):
        x = round(i * x_step, 1)
        y = round(height - ((s - y_min) / (y_max - y_min)) * height, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    last_score = scores[-1]
    color = "#dc2626" if last_score < 60 else "#d97706" if last_score < 75 else "#8A5CF6" if last_score < 90 else "#16a34a"
    trend = scores[-1] - scores[0]
    arrow = "&#9650;" if trend > 0 else "&#9660;" if trend < 0 else "&#8212;"
    arrow_color = "#16a34a" if trend > 0 else "#dc2626" if trend < 0 else "#5E6573"
    return f'<svg width="{width}" height="{height}" style="vertical-align:middle"><polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> <span style="font-size:12px;color:{arrow_color};font-weight:700">{arrow} {abs(trend):+d}</span>'


def summarize_with_claude(sessions, intervention, performing):
    if not ANTHROPIC_API_KEY or not sessions:
        return None, "Claude not configured or no sessions"
    system = """You are a data storyteller for Jack Westin's MCAT tutoring QA program. Given session data from the last 3 days, write a concise narrative (3–4 paragraphs) that:
1. Opens with the key headline: how many sessions, how many tutors, overall trend (improving/declining/stable).
2. Calls out specific tutors needing intervention with concrete details (what SOP areas failed).
3. Highlights tutors who improved or excelled, with specific score changes.
4. Closes with 2–3 prioritized action items for directors.
Write in professional but engaging tone. Use specific names and numbers. Plain text only, no markdown."""
    rows = []
    for s in sessions[:50]:
        rows.append(f"- {s.get('tutor_name')} | Student: {s.get('student_name')} | {s.get('session_date')} | Session {s.get('session_number')} | {s.get('course_type')} | Score {s.get('score')}/100 | {s.get('rating')}")
    int_names = [t["name"] for t in intervention]
    perf_names = [t["name"] for t in performing]
    user_content = (
        f"Period: Last 3 days | Total sessions: {len(sessions)}\n"
        f"Tutors needing intervention: {', '.join(int_names) or 'None'}\n"
        f"Tutors performing well: {', '.join(perf_names) or 'None'}\n\n"
        f"Session details:\n" + "\n".join(rows)
    )
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1500,
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
            text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
            return text.strip(), None
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else str(e)
        return None, body[:300]
    except Exception as e:
        return None, str(e)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_html_digest(sessions, band_counts, intervention, performing, narrative, all_sessions_30d):
    total = len(sessions)
    total_tutors = len(set((s.get("tutor_name") or "").strip() for s in sessions if s.get("tutor_name")))
    avg_score_all = 0
    valid_scores = [s.get("score") for s in sessions if s.get("score") is not None]
    if valid_scores:
        avg_score_all = round(sum(valid_scores) / len(valid_scores))

    # Tutor history from 30-day data for sparklines
    tutor_history = defaultdict(list)
    if all_sessions_30d:
        sorted_30d = sorted(all_sessions_30d, key=lambda s: s.get("created_at", ""))
        for s in sorted_30d:
            name = (s.get("tutor_name") or "").strip()
            score = s.get("score")
            if name and score is not None:
                tutor_history[name].append(score)

    avg_color = "#dc2626" if avg_score_all < 60 else "#d97706" if avg_score_all < 75 else "#8A5CF6" if avg_score_all < 90 else "#16a34a"
    n_int = len(intervention)
    n_perf = len(performing)
    band_total = sum(band_counts.values()) or 1

    def pct(n): return round(n / band_total * 100)

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif">
<div style="max-width:700px;margin:0 auto;padding:24px 16px">

<!-- Header -->
<div style="background:linear-gradient(135deg,#8A5CF6 0%,#B88AFF 100%);border-radius:16px 16px 0 0;padding:28px 32px;text-align:center">
  <div style="display:inline-block;background:rgba(255,255,255,0.2);border-radius:8px;padding:4px 14px;margin-bottom:12px">
    <span style="color:#fff;font-size:11px;font-weight:800;letter-spacing:0.12em">JW SESSION GRADER</span>
  </div>
  <h1 style="color:#fff;font-size:22px;font-weight:700;margin:8px 0 4px">Tutor Progress Report</h1>
  <p style="color:rgba(255,255,255,0.8);font-size:13px;margin:0">Last {DIGEST_DAYS} days · {total} session(s) · {total_tutors} tutor(s)</p>
</div>

<!-- Key metrics row -->
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:20px 32px">
  <table style="width:100%;border-collapse:collapse"><tr>
    <td style="text-align:center;padding:8px 12px;width:25%">
      <div style="font-size:28px;font-weight:800;color:#2B2F40">{total}</div>
      <div style="font-size:11px;font-weight:600;color:#5E6573;text-transform:uppercase;letter-spacing:0.08em">Sessions</div>
    </td>
    <td style="text-align:center;padding:8px 12px;width:25%">
      <div style="font-size:28px;font-weight:800;color:{avg_color}">{avg_score_all}</div>
      <div style="font-size:11px;font-weight:600;color:#5E6573;text-transform:uppercase;letter-spacing:0.08em">Avg Score</div>
    </td>
    <td style="text-align:center;padding:8px 12px;width:25%">
      <div style="font-size:28px;font-weight:800;color:#dc2626">{n_int}</div>
      <div style="font-size:11px;font-weight:600;color:#5E6573;text-transform:uppercase;letter-spacing:0.08em">Need Action</div>
    </td>
    <td style="text-align:center;padding:8px 12px;width:25%">
      <div style="font-size:28px;font-weight:800;color:#16a34a">{n_perf}</div>
      <div style="font-size:11px;font-weight:600;color:#5E6573;text-transform:uppercase;letter-spacing:0.08em">On Track</div>
    </td>
  </tr></table>
</div>

<!-- Score distribution bar -->
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:16px 32px">
  <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#5E6573;margin-bottom:10px">Score Distribution</div>
  <div style="height:24px;border-radius:12px;overflow:hidden;display:flex;background:#f3f4f6">
    {"".join([
        f'<div style="width:{pct(band_counts["remediation"])}%;background:#dc2626;height:24px"></div>' if band_counts["remediation"] else "",
        f'<div style="width:{pct(band_counts["calibration"])}%;background:#d97706;height:24px"></div>' if band_counts["calibration"] else "",
        f'<div style="width:{pct(band_counts["meets"])}%;background:#8A5CF6;height:24px"></div>' if band_counts["meets"] else "",
        f'<div style="width:{pct(band_counts["exceeds"])}%;background:#16a34a;height:24px"></div>' if band_counts["exceeds"] else "",
    ])}
  </div>
  <div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">
    <span style="font-size:11px;color:#dc2626;font-weight:600">&#9632; Remediation ({band_counts["remediation"]})</span>
    <span style="font-size:11px;color:#d97706;font-weight:600">&#9632; Calibration ({band_counts["calibration"]})</span>
    <span style="font-size:11px;color:#8A5CF6;font-weight:600">&#9632; Meets ({band_counts["meets"]})</span>
    <span style="font-size:11px;color:#16a34a;font-weight:600">&#9632; Exceeds ({band_counts["exceeds"]})</span>
  </div>
</div>
"""

    # Intervention section
    html += """
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 32px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
    <div style="width:10px;height:10px;border-radius:50%;background:#dc2626"></div>
    <span style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#dc2626">Tutors Needing Intervention</span>
  </div>
"""
    if intervention:
        for t in intervention:
            bar = build_score_bar_svg(t["worst"], 160)
            sparkline = build_trend_sparkline(tutor_history.get(t["name"], t["scores"]))
            worst_color = "#dc2626" if t["worst"] < 60 else "#d97706"
            ratings_str = ", ".join(set(r for r in t["ratings"] if r in INTERVENTION_RATINGS))
            html += f"""
  <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:16px 18px;margin-bottom:10px">
    <table style="width:100%"><tr>
      <td style="vertical-align:top;width:45%">
        <div style="font-size:15px;font-weight:700;color:#2B2F40;margin-bottom:4px">{esc(t["name"])}</div>
        <div style="font-size:12px;color:#5E6573">{t["count"]} session(s) · {ratings_str or "Below threshold"}</div>
      </td>
      <td style="text-align:center;vertical-align:top;width:25%">
        <div style="font-size:24px;font-weight:800;color:{worst_color}">{t["worst"]}</div>
        <div style="font-size:10px;color:#5E6573;font-weight:600">WORST</div>
      </td>
      <td style="vertical-align:top;text-align:right;width:30%">
        <div style="font-size:10px;color:#5E6573;font-weight:600;margin-bottom:4px">TREND</div>
        {sparkline or '<span style="font-size:11px;color:#9CA3AF">Not enough data</span>'}
      </td>
    </tr></table>
    <div style="margin-top:10px">{bar} <span style="font-size:12px;color:{worst_color};font-weight:700">{t["worst"]}/100</span></div>
  </div>
"""
    else:
        html += '<p style="color:#5E6573;font-size:13px;padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;text-align:center">No tutors need intervention this period.</p>'
    html += "</div>"

    # Performing well section
    html += """
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 32px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
    <div style="width:10px;height:10px;border-radius:50%;background:#16a34a"></div>
    <span style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#16a34a">Tutors On Track</span>
  </div>
"""
    if performing:
        html += '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += '<tr style="border-bottom:2px solid #EDE9FE"><th style="text-align:left;padding:8px 12px;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#5E6573;background:#F9FAFB">Tutor</th><th style="text-align:center;padding:8px 12px;font-size:11px;font-weight:700;color:#5E6573;background:#F9FAFB">Sessions</th><th style="text-align:center;padding:8px 12px;font-size:11px;font-weight:700;color:#5E6573;background:#F9FAFB">Avg Score</th><th style="text-align:right;padding:8px 12px;font-size:11px;font-weight:700;color:#5E6573;background:#F9FAFB">Trend</th></tr>'
        for i, t in enumerate(performing):
            bg = "#fff" if i % 2 == 0 else "#FAFAFF"
            score_color = "#16a34a" if t["avg"] >= 90 else "#8A5CF6"
            sparkline = build_trend_sparkline(tutor_history.get(t["name"], t["scores"]))
            html += f'<tr style="border-bottom:1px solid #E5E7EB"><td style="padding:10px 12px;background:{bg};font-weight:600;color:#2B2F40">{esc(t["name"])}</td><td style="text-align:center;padding:10px 12px;background:{bg};color:#5E6573">{t["count"]}</td><td style="text-align:center;padding:10px 12px;background:{bg};font-weight:700;color:{score_color}">{t["avg"]}/100</td><td style="text-align:right;padding:10px 12px;background:{bg}">{sparkline or "—"}</td></tr>'
        html += "</table>"
    else:
        html += '<p style="color:#5E6573;font-size:13px;text-align:center">No sessions from on-track tutors in this period.</p>'
    html += "</div>"

    # AI narrative section
    html += f"""
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 32px">
  <div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#8A5CF6;border-bottom:1px solid #EDE9FE;padding-bottom:8px;margin-bottom:14px">Analysis & Recommendations</div>
  {"".join(f'<p style="color:#5E6573;font-size:13px;line-height:1.7;margin:6px 0">{esc(para)}</p>' for para in (narrative or "No narrative available.").split(chr(10)) if para.strip())}
</div>
"""

    # Score bands legend + footer
    html += f"""
<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:0 0 16px 16px;padding:16px 32px;text-align:center">
  <span style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#5E6573">Score bands: </span>
  <span style="padding:3px 8px;border-radius:6px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:11px;color:#16a34a;font-weight:600">90-100 Exceeds</span>
  <span style="padding:3px 8px;border-radius:6px;background:#eff6ff;border:1px solid #bfdbfe;font-size:11px;color:#2563eb;font-weight:600;margin-left:4px">75-89 Meets</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fffbeb;border:1px solid #fde68a;font-size:11px;color:#d97706;font-weight:600;margin-left:4px">60-74 Coach</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fef2f2;border:1px solid #fecaca;font-size:11px;color:#dc2626;font-weight:600;margin-left:4px">&lt;60 Remediate</span>
</div>

<p style="text-align:center;font-size:11px;color:#9CA3AF;margin-top:18px">JW Session Grader · Tutor Progress Report · Every {DIGEST_DAYS} days</p>
</div>
</body></html>"""
    return html


def build_plain_text(sessions, intervention, performing, narrative):
    parts = [
        f"JW TUTOR PROGRESS REPORT — Last {DIGEST_DAYS} Days",
        f"{len(sessions)} sessions graded",
        "",
        "=" * 50,
        "TUTORS NEEDING INTERVENTION",
        "=" * 50,
        "",
    ]
    if intervention:
        for t in intervention:
            ratings = ", ".join(set(r for r in t["ratings"] if r in INTERVENTION_RATINGS))
            parts.append(f"  {t['name']} — Worst: {t['worst']}/100 | Avg: {t['avg']}/100 | {t['count']} session(s) | {ratings or 'Below threshold'}")
    else:
        parts.append("  (None)")
    parts += ["", "=" * 50, "TUTORS ON TRACK", "=" * 50, ""]
    for t in performing:
        parts.append(f"  {t['name']} — Avg: {t['avg']}/100 | {t['count']} session(s)")
    parts += ["", "-" * 50, "ANALYSIS & RECOMMENDATIONS", "-" * 50, "", narrative or "No summary.", ""]
    return "\n".join(parts)


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
        sessions, fetch_err = fetch_sessions(days=DIGEST_DAYS)
        if fetch_err:
            self._json(500, {"success": False, "error": fetch_err})
            return

        to_emails = get_director_emails()
        if not to_emails:
            self._json(500, {"success": False, "error": "No director emails configured"})
            return

        if not sessions:
            subject = f"JW Tutor Progress Report — No sessions in last {DIGEST_DAYS} days"
            body = f"No sessions were graded in the last {DIGEST_DAYS} days."
            ok, send_err = send_email(to_emails, subject, body)
            self._json(200 if ok else 500, {"success": ok, "sessions": 0, "sent": ok, "error": send_err})
            return

        # Fetch 30-day history for sparkline trends
        all_30d, _ = fetch_all_sessions_for_tutor_history()
        tutor_data, band_counts, intervention, performing = analyze_sessions(sessions)
        narrative, claude_err = summarize_with_claude(sessions, intervention, performing)
        if claude_err:
            narrative = f"[Summary unavailable: {claude_err}]"

        plain = build_plain_text(sessions, intervention, performing, narrative)
        html = build_html_digest(sessions, band_counts, intervention, performing, narrative, all_30d)
        n_int = len(intervention)
        subject = f"JW Tutor Progress Report — {len(sessions)} session(s) | {n_int} needing intervention"

        ok, send_err = send_email(to_emails, subject, plain, html=html)
        if ok:
            self._json(200, {"success": True, "sessions": len(sessions), "intervention_count": n_int, "sent": True, "to": to_emails})
        else:
            self._json(500, {"success": False, "error": send_err, "sessions": len(sessions)})

    def log_message(self, format, *args):
        pass
