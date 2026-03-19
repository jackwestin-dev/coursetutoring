# Score bands and when to flag for intervention

The Session Grader assigns a score and an **overall rating** to each graded session. Directors receive a **daily digest** that lists tutors needing intervention first, then progress notes.

---

## Score bands by course type

### CARS Strategy (scaled 0–100)

| Score range | Band label | Meaning | Director action |
|-------------|------------|---------|------------------|
| **90–100** | Exceeds Expectations | Strong documentation and coaching; no issues. | None. |
| **75–89** | Meets Expectations | Solid session; meets SOPs. | None. |
| **60–74** | Needs Minor Calibration | Gaps in documentation or delivery; coachable. | **Flag:** Consider follow-up or calibration with the tutor. |
| **<60** | Needs Remediation | Significant gaps; does not meet SOPs. | **Intervention:** Prioritize 1:1 or structured remediation. |

### 515+ Course & Intensive (raw score 0–135)

| Score range | Band label | Meaning | Director action |
|-------------|------------|---------|------------------|
| **120–135** | Excellent | Covers all SOP items, strong coaching, thorough documentation. | None. |
| **100–119** | Satisfactory | Minor gaps but fundamentally solid session. | None. |
| **80–99** | Needs Improvement | Multiple SOP items missed or coaching quality concerns. | **Flag:** Consider follow-up or calibration with the tutor. |
| **<80** | Unsatisfactory | Significant SOP non-compliance or poor coaching. | **Intervention:** Prioritize 1:1 or structured remediation. |

The 515+/Intensive rubric uses 4 categories totaling 135 points:
- **A. SOP Compliance** — 50 pts (37%)
- **B. Coaching Quality** — 50 pts (37%)
- **C. Notes & Documentation** — 20 pts (15%)
- **D. Professionalism** — 15 pts (11%)

---

## Who appears in "Tutors needing intervention"

The **daily email** starts with a section:

**TUTORS NEEDING INTERVENTION (not abiding by SOPs)**

A tutor is included in this list if **any** of their sessions in the last 24 hours had:

- **CARS:** Score < 75, or Rating = "Needs Remediation" or "Needs Minor Calibration"
- **515+/Intensive:** Score < 100, or Rating = "Unsatisfactory" or "Needs Improvement"

So:

- **Unsatisfactory / Needs Remediation** → always listed (urgent).
- **Needs Improvement / Needs Minor Calibration** → always listed (follow-up).
- **Satisfactory / Meets** or above → not listed.

The list is **one line per tutor** (no duplicate names); the line shows their worst score/rating in that period.

---

## How to use the daily digest

1. **Read the intervention list first** — these are the tutors to follow up with.
2. **Unsatisfactory/Remediation** — schedule intervention; do not wait.
3. **Needs Improvement/Minor Calibration** — assign coaching or calibration as needed.
4. Use the **Progress & notes** section for volume and positives; the intervention list drives action.

---

## Where the data comes from

- Sessions are **manually entered** in the Session Grader app (paste transcript + student notes, then Grade).
- Each graded session is stored in **Supabase** (`session_records`).
- The **daily digest** (cron) reads the last 24 hours from Supabase, builds the intervention list, then emails directors.

See **VERCEL_EMAIL_SETUP.md** for SMTP and **DIRECTOR_EMAILS** so the daily email is delivered.
