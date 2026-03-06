# Score bands and when to flag for intervention

The Session Grader assigns a **scaled score (0–100)** and an **overall rating** to each graded session. Directors receive a **daily digest** that lists tutors needing intervention first, then progress notes.

---

## Score bands (how we flag)

| Score range | Band label | Meaning | Director action |
|-------------|------------|---------|------------------|
| **90–100** | Exceeds Expectations | Strong documentation and coaching; no issues. | None. |
| **75–89** | Meets Expectations | Solid session; meets SOPs. | None. |
| **60–74** | Needs Minor Calibration | Gaps in documentation or delivery; coachable. | **Flag:** Consider follow-up or calibration with the tutor. |
| **&lt;60** | Needs Remediation | Significant gaps; does not meet SOPs. | **Intervention:** Prioritize 1:1 or structured remediation. |

---

## Who appears in “Tutors needing intervention”

The **daily email** starts with a section:

**TUTORS NEEDING INTERVENTION (not abiding by SOPs)**

A tutor is included in this list if **any** of their sessions in the last 24 hours had:

- **Score &lt; 75**, or  
- **Rating** = “Needs Remediation” or “Needs Minor Calibration”

So:

- **Needs Remediation** → always listed (urgent).
- **Needs Minor Calibration** → always listed (follow-up).
- **Score 60–74** with a “Meets”-style label → still listed (below 75).
- **Score 75+** and “Meets” or “Exceeds” → not listed.

The list is **one line per tutor** (no duplicate names); the line shows their worst score/rating in that period.

---

## How to use the daily digest

1. **Read the intervention list first** — these are the tutors to follow up with.
2. **Remediation (&lt;60 / “Needs Remediation”)** — schedule intervention; do not wait.
3. **Minor calibration (60–74 / “Needs Minor Calibration”)** — assign coaching or calibration as needed.
4. Use the **Progress & notes** section for volume and positives; the intervention list drives action.

---

## Where the data comes from

- Sessions are **manually entered** in the Session Grader app (paste transcript + student notes, then Grade).
- Each graded session is stored in **Supabase** (`session_records`).
- The **daily digest** (cron) reads the last 24 hours from Supabase, builds the intervention list, then emails directors.

See **VERCEL_EMAIL_SETUP.md** for SMTP and **DIRECTOR_EMAILS** so the daily email is delivered.
