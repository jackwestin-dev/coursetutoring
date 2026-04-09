# Score bands and when to flag for intervention

The Session Grader assigns a score and an **overall rating** to each graded session. Directors receive a **daily digest** that lists tutors needing intervention first, then progress notes.

---

## Score bands by course type

### CARS Strategy (125 points)

| Raw score | % of max | Band label | Meaning | Director action |
|-----------|----------|------------|---------|------------------|
| **112–125** | 89–100% | Excellent | Strong documentation and coaching; no issues. | None. |
| **93–111** | 74–88% | Satisfactory | Solid session; meets SOPs. | None. |
| **74–92** | 59–73% | Needs Improvement | Multiple SOP items missed or coaching quality concerns. | **Flag:** Consider follow-up or calibration with the tutor. |
| **<74** | <59% | Unsatisfactory | Significant SOP non-compliance or poor coaching. | **Intervention:** Prioritize 1:1 or structured remediation. |

The CARS rubric uses 4 categories totaling 125 points:
- **A. SOP Compliance** — 45 pts (36%)
- **B. Coaching Quality** — 45 pts (36%)
- **C. Notes & Documentation** — 20 pts (16%)
- **D. Professionalism** — 15 pts (12%)

### 515+ Course & Intensive (135 points)

| Raw score | % of max | Band label | Meaning | Director action |
|-----------|----------|------------|---------|------------------|
| **120–135** | 89–100% | Excellent | Covers all SOP items, strong coaching, thorough documentation. | None. |
| **100–119** | 74–88% | Satisfactory | Minor gaps but fundamentally solid session. | None. |
| **80–99** | 59–73% | Needs Improvement | Multiple SOP items missed or coaching quality concerns. | **Flag:** Consider follow-up or calibration with the tutor. |
| **<80** | <59% | Unsatisfactory | Significant SOP non-compliance or poor coaching. | **Intervention:** Prioritize 1:1 or structured remediation. |

The 515+/Intensive rubric uses 4 categories totaling 135 points:
- **A. SOP Compliance** — 50 pts (37%)
- **B. Coaching Quality** — 50 pts (37%)
- **C. Notes & Documentation** — 20 pts (15%)
- **D. Professionalism** — 15 pts (11%)

---

## Who appears in "Tutors needing intervention"

The **daily email** starts with a section:

**TUTORS NEEDING INTERVENTION (not abiding by SOPs)**

A tutor is included in this list if **any** of their sessions in the digest period had a rating of:

- **Unsatisfactory** → always listed (urgent).
- **Needs Improvement** → always listed (follow-up).
- **Satisfactory** or **Excellent** → not listed.

The list is **one line per tutor** (no duplicate names); the line shows their worst score/rating in that period. Scores are shown as a **% of max** so CARS (125-pt) and 515+/Intensive (135-pt) sessions are comparable.

---

## How to use the daily digest

1. **Read the intervention list first** — these are the tutors to follow up with.
2. **Unsatisfactory** — schedule intervention; do not wait.
3. **Needs Improvement** — assign coaching or calibration as needed.
4. Use the **Progress & notes** section for volume and positives; the intervention list drives action.

---

## Where the data comes from

- Sessions are **manually entered** in the Session Grader app (paste transcript + student notes, then Grade).
- Each graded session is stored in **Supabase** (`session_records`).
- The **daily digest** (cron) reads the last 3 days from Supabase, builds the intervention list, then emails directors.

See **VERCEL_EMAIL_SETUP.md** for SMTP and **DIRECTOR_EMAILS** so the daily email is delivered.
