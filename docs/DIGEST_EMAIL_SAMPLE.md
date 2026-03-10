# Director digest email (every 3 days) — sample output

The digest is sent by **`/api/director-digest`** on a Vercel Cron schedule (every 3 days). Each director in `DIRECTOR_EMAILS` gets one email.

---

## Subject line

- With sessions: **`JW Tutor Progress Report — 12 session(s) | 2 needing intervention`**
- No sessions: **`JW Tutor Progress Report — No sessions in last 3 days`**

---

## Plain-text version (sample)

```
JW TUTOR PROGRESS REPORT — Last 3 Days
12 sessions graded

==================================================
TUTORS NEEDING INTERVENTION
==================================================

  Jordan Lee — Worst: 58/100 | Avg: 72/100 | 3 session(s) | Needs Remediation
  Sam Chen — Worst: 62/100 | Avg: 68/100 | 2 session(s) | Needs Minor Calibration

==================================================
TUTORS ON TRACK
==================================================

  Alex Rivera — Avg: 94/100 | 4 session(s)
  Morgan Taylor — Avg: 88/100 | 3 session(s)

--------------------------------------------------
ANALYSIS & RECOMMENDATIONS
--------------------------------------------------

[AI-generated narrative from Claude: 3–4 paragraphs with headline, 
intervention callouts, highlights, and 2–3 action items.]

JW Session Grader · Tutor Progress Report · Every 3 days
```

---

## HTML version (structure)

The HTML email includes:

1. **Header**  
   Purple gradient banner: “JW SESSION GRADER”, “Tutor Progress Report”, “Last 3 days · X session(s) · Y tutor(s)”.

2. **Key metrics row**  
   Four numbers: **Sessions**, **Avg Score**, **Need Action** (intervention count), **On Track** (performing count).

3. **Score distribution bar**  
   Horizontal stacked bar: Remediation (red), Calibration (amber), Meets (purple), Exceeds (green), with counts.

4. **Tutors Needing Intervention**  
   Red-accent section. For each tutor: name, session count, rating badges, **worst score** (large), **trend** (sparkline + arrow), and a score bar.

5. **Tutors On Track**  
   Green-accent section. Table: Tutor name, Sessions, Avg Score, Trend (sparkline).

6. **Analysis & Recommendations**  
   Purple-accent heading; body is the AI narrative (paragraphs from Claude).

7. **Footer**  
   Score bands legend (90–100 Exceeds, 75–89 Meets, 60–74 Coach, &lt;60 Remediate) and “JW Session Grader · Tutor Progress Report · Every 3 days”.

---

## When there are no sessions

- **Subject:** `JW Tutor Progress Report — No sessions in last 3 days`
- **Body:** “No sessions were graded in the last 3 days.” (plain text only; no HTML sections).

---

## How to trigger it manually

- **Cron:** Runs automatically every 3 days (see `vercel.json` crons).
- **Manual test:** Open in browser or call with `curl`:
  - `https://<your-app>.vercel.app/api/director-digest`

You’ll get JSON (e.g. `{"success": true, "sessions": 12, "intervention_count": 2, "sent": true, "to": ["..."]}`) and all directors will receive the digest email.
