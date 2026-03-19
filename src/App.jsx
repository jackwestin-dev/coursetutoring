import { useState, useRef } from "react";

// ─── Grading system prompt ────────────────────────────────────────────────────
const GRADING_PROMPT = `You are the JW CARS Session Grader, an internal QA agent for Jack Westin MCAT CARS Strategy Course tutoring.

CORE GRADING RULES
1. Grade the NOTES primarily. Transcript reveals what SHOULD be documented and assesses live coaching quality.
2. Evidence must be explicit. No credit for implied content. Partial credit when partial documentation exists.
3. Score conservatively when uncertain.
4. AAMC DUAL-SOURCE RULE: For AAMC scheduling/sequencing, check BOTH the transcript AND the student notes document. If EITHER source confirms AAMC materials were assigned/scheduled/completed, award full credit. Only deduct if BOTH sources fail to confirm. The student notes document saying "yes" to assigning all AAMC documents is sufficient on its own.
5. SOP VERIFICATION INPUTS (THIRD SOURCE OF TRUTH): The grader may provide manual SOP verification inputs for: study schedule, AAMC question packs, and full-length exams. These are a fail-safe alongside transcript and student notes. Scoring: YES = full credit for that sub-item, PARTIAL = 50% credit, NO = 0 points UNLESS transcript or student notes confirm otherwise. Any source confirming the item can override a "No" from another source.

SESSION 1 RUBRIC — Onboarding & Plan Build (90 pts documentation + 60 pts coaching = 150 total, scaled to 100)
PASS/FAIL GATES: Session Notes Template copied and completed | Strategy Portion completed (teach-back occurred) | Study Plan updated | Fathom summary forwarded (mark Unable to Verify)

A. Preparation & Planning Readiness — 18 pts
   18: Test date confirmed, baseline CARS score reviewed, JW mapping principles noted, below-average areas identified
   14: Most elements present  9: Test date/goals only  4: Mostly reactive  0: No prep

B. Study Plan Construction Quality — 30 pts
   30: 10 FLs scheduled with dates (JW FL 1-6 + AAMC exams), AAMC question pack scheduling (if student has them), weekly checklist, Week 1 daily tasks, HW Tracker link
   22: Strong plan  15: Exists but lacks specificity  8: General advice only  0: No plan

C. Personalization & Load Calibration — 13 pts
   13: Adapted to availability/timeline  10: Availability acknowledged  6: Some personalization  3: Constraints mentioned  0: None

D. Strategy Portion Execution — 23 pts
   23: Student taught back; per-paragraph feedback; 3+ questions; missed reasons identified; videos recommended
   17: Teach-back + some questions  11: Mostly tutor-led  5: Brief mention  0: No teach-back (auto 0)

E. Clarity & Student Buy-In — 9 pts
   9: Takeaways verbalized; next steps explicit; next session scheduled; HW Tracker explained
   7: Plan summarized  4: Clarity not verified  2: Unclear  0: None

SESSION 1 SOP CHECKLIST: Student Overview completed | Passage video takeaways | 10 FL exam schedule (JW FL 1-6 + AAMC exams) | AAMC question packs/resources scheduling (conditional — only if student has them; full credit if student has none) | Weekly checklist | Week 1 daily tasks | Strategy notes | 2+ video recs | HW Tracker link | Next session date | Fathom forwarded

FULL-LENGTH EXAMS vs. AAMC QUESTION PACKS — These are scored SEPARATELY:
- Full-Length Exams (mandatory): 10 exams must be scheduled. Sources: Jack Westin FL 1-6 + AAMC exams. Keywords: "exam", "full length", "JW FL", "AAMC exam".
- AAMC Question Packs/Resources (conditional): 10 specific AAMC resources (Bio QP Vol 1&2, Chem QP, Physics QP, CARS QP Vol 1&2, Section Bank, Official Prep Hub Question Bank, CARS Diagnostic Tool, Flashcards). Only required IF student has them. Full credit if student has none.
- Detection: "AAMC exam" = full-length exam. "AAMC question pack/section bank/flashcards" = AAMC resource.
- Dual-source rule: Evidence from either transcript or student notes is valid.
- CRITICAL DEFAULT DATE: The student notes sheet has a default/placeholder date of "March 5" (Mar 5, 3/5, 03/05) pre-filled in the Planned Date column. If exams show this date, the tutor did NOT schedule them — they left the default. Exams with March 5th do NOT count as scheduled. Only exams with dates OTHER than March 5th count. If all/most exams show March 5th, award zero for FL scheduling.

SESSION 2 RUBRIC — Adherence & Adjustment (90+60=150, scaled to 100)
PASS/FAIL GATES: same as Session 1
A. Prep & Data Review — 14 pts  B. Accountability & Reflection — 23 pts  C. Plan Adjustment Quality — 18 pts  D. Time Management Coaching — 14 pts  E. Strategy Portion Execution — 21 pts
SESSION 2 SOP: HW Tracker status | Timed section reviewed | 5 reflection areas | Roadblocks noted | Updated schedule | Strategy notes | Next session | Fathom forwarded

SESSION 3 RUBRIC — Timed Pressure & Diagnostics (90+60=150, scaled to 100)
PASS/FAIL GATES: same as Session 1
A. Diagnostic Design Quality — 18 pts  B. Accountability Enforcement — 18 pts  C. Timing & Accuracy Analysis — 23 pts  D. Personalized Coaching Using Visuals — 13 pts  E. Strategy Portion Execution — 18 pts
SESSION 3 SOP: Timed section assigned+done | 5 reflection areas | Timing data | Per-passage insights | Personalized timing advice | Updated plan | Test-day strategy | Fathom forwarded

UNIVERSAL TEACHING QUALITY — from TRANSCRIPT (60 pts):
A. Approachability 12pts  B. CARS Passage Framing 18pts  C. CARS Question Approach 18pts  D. Student Metacognition 12pts
TUTOR MISTAKE FLAGS: >2min monologue | Re-mapping for student | Ignoring "I just guessed/silly mistake" | Ending without written next steps | Only discussing accuracy

OUTPUT — produce exactly this markdown:
---
## SECTION 1: QUICK VERDICT
| Field | Value |
|-------|-------|
| Student | [name] |
| Tutor | [name] |
| Session | [1/2/3] |
| Session Date | [date] |
| Overall Rating | [Exceeds Expectations / Meets Expectations / Needs Minor Calibration / Needs Remediation] |
| Biggest Risk | [1 sentence] |

**Pass/Fail Gates:**
- Notes Template: [PASS / FAIL]
- Strategy Portion: [PASS / FAIL]
- Study Plan Updated: [PASS / FAIL]
- Fathom Forwarded: [Unable to Verify]

**Top 3 Fixes:**
1. [fix]
2. [fix]
3. [fix]

---
## SECTION 2: CATEGORY SCORES
### A. [Name] — [score]/[max] pts
**Justification:** [2-3 sentences]
**Missing from Notes:**
- [bullets]
[repeat B-E]

---
## SECTION 3: SOP COMPLIANCE CHECKLIST
| SOP Item | Status | Evidence |
|----------|--------|----------|
[all items]
**Compliance Summary:** [X] fully met, [Y] partial, [Z] missing

---
## SECTION 4: TRANSCRIPT COACHING QUALITY
| Behavior | Score | Observation |
|----------|-------|-------------|
| Approachability | X/12 | [evidence] |
| CARS Passage Framing | X/18 | [evidence] |
| CARS Question Approach | X/18 | [evidence] |
| Student Metacognition | X/12 | [evidence] |
| **Subtotal** | **X/60** | |
**Tutor Mistakes Flagged:**
- [list or "None observed"]

---
## SECTION 5: TRANSCRIPT vs. NOTES GAP ANALYSIS
| Topic Discussed | In Notes? | Impact |
|-----------------|-----------|--------|
[key topics]

---
## SECTION 6: TUTOR FEEDBACK
### What You Did Well
1. [positive with evidence]
2. [positive with evidence]
3. [positive with evidence]

### Areas for Improvement
1. **[Issue Title]**
   - What happened: [desc]
   - Why it matters: [impact]
   - How to fix: [guidance]

---
## SECTION 7: FINAL SCORE SUMMARY
| Category | Score | Max |
|----------|-------|-----|
| A. [Name] | X | XX |
| B. [Name] | X | XX |
| C. [Name] | X | XX |
| D. [Name] | X | XX |
| E. [Name] | X | XX |
| Teaching Quality | X | 60 |
| **TOTAL** | **X** | **150** |
**Scaled Score:** X/100
**Overall Assessment:** [rating]
**Summary:** [3-4 sentences]

Bands: 90-100=Exceeds, 75-89=Meets, 60-74=Needs Minor Calibration, <60=Needs Remediation. Any failed gate=Needs Remediation.`;

// 515+ Course & Intensive — 4-category 135-point rubric (Sessions 1-3)
const ORIGINAL_GRADING_PROMPT = `You are the JW Session Grader for the 515+ MCAT Course and Intensive course. Grade using the 515+/Intensive 135-point rubric (NOT the CARS-specific rubric).

CORE GRADING RULES
1. Grade the NOTES primarily. Transcript reveals what SHOULD be documented and assesses live coaching quality.
2. Evidence must be explicit. No credit for implied content.
3. Score conservatively when uncertain.
4. AAMC DUAL-SOURCE RULE: For AAMC scheduling, check BOTH the transcript AND the student notes document. If EITHER source confirms AAMC materials were assigned/scheduled/completed, award full credit. Only deduct if BOTH sources fail to confirm.
5. SOP VERIFICATION INPUTS (THIRD SOURCE OF TRUTH): The grader may provide manual SOP verification inputs for: study schedule, AAMC question packs, and full-length exams. Scoring: YES = full credit, PARTIAL = 50% credit, NO = 0 points UNLESS transcript or student notes confirm otherwise. Any source confirming the item can override a "No" from another source.
6. Most items are BINARY: full points or zero. Did it or didn't. Partial credit ONLY where explicitly noted.
7. Three sources of truth: transcript, student notes document, and manual SOP verification inputs. If ANY source confirms an item, give credit.

FULL-LENGTH EXAMS vs. AAMC QUESTION PACKS — scored SEPARATELY:
- Full-Length Exams (mandatory): 10 exams scheduled with real dates. Sources: Jack Westin FL 1-6 + AAMC exams.
- AAMC Question Packs/Resources (conditional): Bio QP Vol 1&2, Chem QP, Physics QP, CARS QP Vol 1&2, Section Bank, Official Prep Hub, CARS Diagnostic Tool, Flashcards. Only if student has them. Auto full credit if student has none.
- CRITICAL DEFAULT DATE: "March 5" (Mar 5, 3/5, 03/05) is a placeholder date pre-filled in the student notes sheet. Exams with March 5th do NOT count as scheduled. Only exams with dates OTHER than March 5th count. If all/most exams show March 5th, award zero for FL scheduling.

=== RUBRIC: 4 CATEGORIES, 135 POINTS TOTAL ===

## A. SOP COMPLIANCE — 50 Points

### A1. Session Structure & Timing (10 pts)
- Follows SOP time blocks (intro, strategy, wrap-up) — 4 pts [binary]
- Covers all required agenda items for that session — 4 pts [binary]
- Doesn't skip or rush wrap-up section — 2 pts [binary]

### A2. Study Schedule & Exam Planning (14 pts)
- Study schedule created in Google Sheet — 4 pts [binary]
- 10 full-length exams scheduled with real dates (NOT March 5 placeholders) — 6 pts [proportional credit allowed: e.g. 7/10 exams = ~4 pts]
- AAMC question packs assigned (if student has them; auto full credit if student doesn't) — 4 pts [binary]

### A3. Pre-Session & Post-Session Tasks (12 pts)
- Pre-session notes completed before session — 3 pts [binary]
- Student overview/survey data reviewed — 3 pts [binary]
- Post-session: in-session notes completed — 3 pts [binary]
- Post-session: notes shared with directors — 3 pts [binary]

### A4. Session-Specific Requirements (14 pts) — ONLY evaluate items for the actual session number:
- S1 ONLY: Booking link shared for next session — 3 pts [binary]
- S1 ONLY: 2+ strategy videos recommended — 3 pts [binary]
- S2 ONLY: FL review process coached — 4 pts [binary]
- S3 ONLY: Test-day toolkit verbalized by student — 4 pts [binary]
Session 1 max for A4: 6 pts (booking link 3 + videos 3). Session 2 max for A4: 4 pts. Session 3 max for A4: 4 pts.
Remaining points in A4 for sessions that don't use all 14 are simply not scored — do NOT penalize.

## B. COACHING QUALITY — 50 Points

### B1. Socratic Method & Guided Questioning (15 pts)
- Uses probing questions vs. lecturing — 5 pts [binary]
- Student does most of the talking — 5 pts [binary]
- Doesn't re-map passages for the student — 5 pts [binary]

### B2. Weakness Identification & Feedback (15 pts)
- Clearly identifies missed question reasons — 5 pts [binary]
- Doesn't let excuses slide — 5 pts [binary]
- Provides actionable, specific strategies — 5 pts [binary]

### B3. Passage Practice Execution (10 pts)
- 3+ questions reviewed together — 4 pts [binary]
- Student teaches passage back (not tutor) — 3 pts [binary]
- Constructive feedback ~once per paragraph — 3 pts [binary]

### B4. Student Engagement & Takeaways (10 pts)
- Asks student for main takeaway(s) — 4 pts [binary]
- Asks if student has questions/concerns — 3 pts [binary]
- Addresses timing AND accuracy (not just one) — 3 pts [binary]

## C. NOTES & DOCUMENTATION — 20 Points
- Student notes template properly named and linked — 3 pts [binary]
- Student Overview tab completed — 3 pts [binary]
- In-session notes are detailed and specific — 5 pts [binary]
- Exam Progress tab updated — 3 pts [binary]
- Next steps clearly written (not just verbal) — 3 pts [binary]
- Added to Activity Completion Tracking (Col M) — 3 pts [binary]

## D. PROFESSIONALISM — 15 Points
- Calm, confident, supportive demeanor — 3 pts [binary]
- Doesn't guarantee outcomes or promise scores — 3 pts [binary]
- Refers students to proper channels (not pricing) — 3 pts [binary]
- Session starts/ends on time — 3 pts [binary]
- Communication on approved platforms only — 3 pts [binary]

=== GRADE SCALE ===
Excellent: 120-135 (89-100%) — Covers all SOP items, strong coaching, thorough documentation
Satisfactory: 100-119 (74-88%) — Minor gaps but fundamentally solid session
Needs Improvement: 80-99 (59-73%) — Multiple SOP items missed or coaching quality concerns
Unsatisfactory: Below 80 (<59%) — Significant SOP non-compliance or poor coaching

=== OUTPUT FORMAT ===
Produce exactly this markdown:

---
## SECTION 1: QUICK VERDICT
| Field | Value |
|-------|-------|
| Student | [name] |
| Tutor | [name] |
| Session | [1/2/3] |
| Session Date | [date] |
| Overall Rating | [Excellent / Satisfactory / Needs Improvement / Unsatisfactory] |
| Biggest Risk | [1 sentence] |

**Top 3 Fixes:**
1. [fix]
2. [fix]
3. [fix]

---
## SECTION 2: CATEGORY SCORES

### A. SOP Compliance — [score]/50 pts
#### A1. Session Structure & Timing — [score]/10
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Follows SOP time blocks | 4 | [0 or 4] | [evidence] |
| Covers all required agenda items | 4 | [0 or 4] | [evidence] |
| Doesn't skip/rush wrap-up | 2 | [0 or 2] | [evidence] |

#### A2. Study Schedule & Exam Planning — [score]/14
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Study schedule in Google Sheet | 4 | [0 or 4] | [evidence] |
| 10 FLs scheduled with real dates | 6 | [0-6] | [evidence, note March 5 detection] |
| AAMC question packs assigned | 4 | [0 or 4] | [evidence or "auto full credit — student has none"] |

#### A3. Pre-Session & Post-Session Tasks — [score]/12
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Pre-session notes completed | 3 | [0 or 3] | [evidence] |
| Student overview/survey reviewed | 3 | [0 or 3] | [evidence] |
| In-session notes completed | 3 | [0 or 3] | [evidence] |
| Notes shared with directors | 3 | [0 or 3] | [evidence] |

#### A4. Session-Specific Requirements — [score]/[session max]
[Only list items for this session number]
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| [session-specific item] | X | [0 or X] | [evidence] |

### B. Coaching Quality — [score]/50 pts
#### B1. Socratic Method & Guided Questioning — [score]/15
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Uses probing questions vs. lecturing | 5 | [0 or 5] | [evidence] |
| Student does most of the talking | 5 | [0 or 5] | [evidence] |
| Doesn't re-map passages for student | 5 | [0 or 5] | [evidence] |

#### B2. Weakness Identification & Feedback — [score]/15
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Clearly identifies missed question reasons | 5 | [0 or 5] | [evidence] |
| Doesn't let excuses slide | 5 | [0 or 5] | [evidence] |
| Provides actionable, specific strategies | 5 | [0 or 5] | [evidence] |

#### B3. Passage Practice Execution — [score]/10
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| 3+ questions reviewed together | 4 | [0 or 4] | [evidence] |
| Student teaches passage back | 3 | [0 or 3] | [evidence] |
| Feedback ~once per paragraph | 3 | [0 or 3] | [evidence] |

#### B4. Student Engagement & Takeaways — [score]/10
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Asks student for main takeaway(s) | 4 | [0 or 4] | [evidence] |
| Asks if student has questions/concerns | 3 | [0 or 3] | [evidence] |
| Addresses timing AND accuracy | 3 | [0 or 3] | [evidence] |

### C. Notes & Documentation — [score]/20 pts
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Notes template properly named/linked | 3 | [0 or 3] | [evidence] |
| Student Overview tab completed | 3 | [0 or 3] | [evidence] |
| In-session notes detailed and specific | 5 | [0 or 5] | [evidence] |
| Exam Progress tab updated | 3 | [0 or 3] | [evidence] |
| Next steps clearly written | 3 | [0 or 3] | [evidence] |
| Added to Activity Completion Tracking | 3 | [0 or 3] | [evidence] |

### D. Professionalism — [score]/15 pts
| Item | Pts | Awarded | Evidence |
|------|-----|---------|----------|
| Calm, confident, supportive demeanor | 3 | [0 or 3] | [evidence] |
| Doesn't guarantee outcomes/scores | 3 | [0 or 3] | [evidence] |
| Refers to proper channels (not pricing) | 3 | [0 or 3] | [evidence] |
| Session starts/ends on time | 3 | [0 or 3] | [evidence] |
| Communication on approved platforms | 3 | [0 or 3] | [evidence] |

---
## SECTION 3: TRANSCRIPT vs. NOTES GAP ANALYSIS
| Topic Discussed | In Notes? | Impact |
|-----------------|-----------|--------|
[key topics]

---
## SECTION 4: TUTOR FEEDBACK
### What You Did Well
1. [positive with evidence]
2. [positive with evidence]

### Areas for Improvement
1. **[Issue Title]**
   - What happened: [desc]
   - Why it matters: [impact]
   - How to fix: [guidance]

---
## SECTION 5: FINAL SCORE SUMMARY
| Category | Score | Max |
|----------|-------|-----|
| A. SOP Compliance | X | 50 |
|   A1. Session Structure & Timing | X | 10 |
|   A2. Study Schedule & Exam Planning | X | 14 |
|   A3. Pre/Post-Session Tasks | X | 12 |
|   A4. Session-Specific Requirements | X | [session max] |
| B. Coaching Quality | X | 50 |
|   B1. Socratic Method | X | 15 |
|   B2. Weakness Identification | X | 15 |
|   B3. Passage Practice | X | 10 |
|   B4. Student Engagement | X | 10 |
| C. Notes & Documentation | X | 20 |
| D. Professionalism | X | 15 |
| **TOTAL** | **X** | **135** |
**Overall Assessment:** [Excellent / Satisfactory / Needs Improvement / Unsatisfactory]
**Summary:** [3-4 sentences]

Grade Scale: 120-135=Excellent, 100-119=Satisfactory, 80-99=Needs Improvement, <80=Unsatisfactory.`;

const EMAIL_PROMPT = `You are a professional email writer for Jack Westin's MCAT tutoring program. Given a grading report, produce TWO emails as JSON only — no markdown fences, no preamble:
{"tutorEmail":{"subject":"...","body":"..."},"managementEmail":{"subject":"...","body":"..."}}

TUTOR EMAIL: Subject "Session [N] Grading Report — [Student Name]". Address tutor by first name. Open with 1-2 sentences on what they did well. Then full graded report in plain text: SESSION [N] GRADING REPORT / Student/Tutor/Date / QUICK VERDICT (rating, score, risk, top 3 fixes) / CATEGORY SCORES A-E (score, justification, missing items) / SOP CHECKLIST / COACHING QUALITY / TUTOR FEEDBACK (what went well + areas for improvement) / FINAL SCORE. Close warmly. Sign: "The JW QA Team"

MANAGEMENT EMAIL: Subject "Session [N] QA — [Tutor Name] | [Score]/[Max] | [Rating]". Use the SCORE and MAX provided in the input (e.g. 95/135 or 82/100). Open with TRIAGE block:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIAGE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tutor: [name] | Student: [name] | Session: [N] | Date: [date]
Score: [X]/[Max] | Rating: [rating]
Action Required: [YES — immediate follow-up / MONITOR — check next session / NONE — on track]

SCORE BAND GUIDE (use whichever matches the rubric):
For CARS (/100): 90-100 Exceeds | 75-89 Meets | 60-74 Coach | <60 Remediate
For 515+/Intensive (/135): 120-135 Excellent | 100-119 Satisfactory | 80-99 Needs Improvement | <80 Unsatisfactory
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Then 3-5 sentence management summary. Then divider + full tutor email draft. Sign: "JW QA System — automated report"`;

// ─── Report line classification (bold headers + indent) ────────────────────────
function isReportMainSection(line) {
  const t = (line || "").trim().replace(/\*\*/g, "");
  return /^Top 3 Fixes/i.test(t) || /^CATEGORY SCORES/i.test(t) || /^S\.?O\.?P\.?\s*CHECKLIST/i.test(t) || /^COACHING QUALITY/i.test(t) || /^TUTOR FEEDBACK/i.test(t) || /^FINAL SCORE/i.test(t);
}
function isReportCategoryLine(line) {
  return /^[A-E]\.\s+.+[—\-].*\d+\/\d+\s*pts/i.test((line || "").trim());
}
function isReportSubsection(line) {
  const t = (line || "").trim().replace(/\*\*/g, "");
  return /^What Went Well/i.test(t) || /^Areas for Improvement/i.test(t);
}

// ─── UI helpers ───────────────────────────────────────────────────────────────
function ReportRenderer({ text }) {
  const lines = text.split("\n");
  const out = [];
  let i = 0;
  const sectionStyle = { fontSize: 13, fontWeight: 700, color: "#2B2F40", marginTop: 24, marginBottom: 10 };
  const categoryStyle = { fontSize: 13, fontWeight: 700, color: "#2B2F40", marginTop: 14, marginBottom: 6, paddingLeft: 16 };
  const subsectionStyle = { fontSize: 13, fontWeight: 700, color: "#2B2F40", marginTop: 12, marginBottom: 6, paddingLeft: 12 };
  const bodyStyle = { color: "#5E6573", fontSize: 13, lineHeight: 1.7, margin: "6px 0", paddingLeft: 12 };
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("## ")) {
      out.push(<h2 key={i} style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A5CF6", borderBottom: "1px solid #EDE9FE", paddingBottom: 8, marginTop: 32, marginBottom: 14 }}>{line.replace("## ", "")}</h2>);
    } else if (line.startsWith("### ")) {
      out.push(<h3 key={i} style={{ fontSize: 14, fontWeight: 600, color: "#2B2F40", marginTop: 20, marginBottom: 6 }}>{line.replace("### ", "")}</h3>);
    } else if (isReportMainSection(line)) {
      const clean = line.replace(/\*\*/g, "").trim();
      out.push(<p key={i} style={sectionStyle}>{clean}</p>);
    } else if (isReportCategoryLine(line)) {
      out.push(<p key={i} style={categoryStyle} dangerouslySetInnerHTML={{ __html: line.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} />);
    } else if (isReportSubsection(line)) {
      const clean = line.replace(/\*\*/g, "").trim();
      out.push(<p key={i} style={subsectionStyle}>{clean}</p>);
    } else if (line.startsWith("| ")) {
      const tLines = [];
      while (i < lines.length && lines[i].startsWith("|")) { tLines.push(lines[i]); i++; }
      const rows = tLines.filter(l => !/^\|[-:\s|]+\|$/.test(l));
      out.push(
        <div key={`t${i}`} style={{ overflowX: "auto", margin: "12px 0", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>{rows.map((row, ri) => {
              const cells = row.split("|").slice(1, -1);
              const isH = ri === 0;
              return <tr key={ri} style={{ borderBottom: ri < rows.length - 1 ? "1px solid #E5E7EB" : "none" }}>
                {cells.map((cell, ci) => {
                  const clean = cell.trim().replace(/\*\*/g, "");
                  return isH
                    ? <th key={ci} style={{ textAlign: "left", padding: "8px 14px", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#5E6573", background: "#F9FAFB", borderBottom: "2px solid #EDE9FE" }}>{clean}</th>
                    : <td key={ci} style={{ padding: "8px 14px", color: "#2B2F40", background: ri % 2 === 0 ? "#fff" : "#FAFAFF", fontSize: 13 }}>{clean}</td>;
                })}
              </tr>;
            })}</tbody>
          </table>
        </div>
      );
      continue;
    } else if (/^\d+\.\s/.test(line)) {
      out.push(<div key={i} style={{ display: "flex", gap: 10, margin: "8px 0", paddingLeft: 12, alignItems: "flex-start" }}><span style={{ color: "#8A5CF6", fontWeight: 700, fontSize: 13, minWidth: 20 }}>{line.match(/^(\d+)\./)[1]}.</span><span style={{ color: "#5E6573", fontSize: 13, lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: line.replace(/^\d+\.\s/, "").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} /></div>);
    } else if (line.startsWith("- ")) {
      out.push(<div key={i} style={{ display: "flex", gap: 9, margin: "6px 0", paddingLeft: 12, alignItems: "flex-start" }}><span style={{ color: "#8A5CF6", fontSize: 8, marginTop: 6, flexShrink: 0 }}>●</span><span style={{ color: "#5E6573", fontSize: 13, lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: line.replace(/^-\s/, "").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} /></div>);
    } else if (line.startsWith("**") && line.endsWith("**")) {
      out.push(<p key={i} style={{ fontWeight: 700, color: "#2B2F40", margin: "12px 0 6px", paddingLeft: 12, fontSize: 13 }}>{line.replace(/\*\*/g, "")}</p>);
    } else if (line === "---") {
      out.push(<hr key={i} style={{ border: "none", borderTop: "1px solid #E5E7EB", margin: "24px 0" }} />);
    } else if (!line.trim()) {
      out.push(<div key={i} style={{ height: 8 }} />);
    } else {
      out.push(<p key={i} style={bodyStyle} dangerouslySetInnerHTML={{ __html: line.replace(/\*\*([^*]+)\*\*/g, "<strong style='color:#2B2F40'>$1</strong>") }} />);
    }
    i++;
  }
  return <div>{out}</div>;
}

function RatingBadge({ rating }) {
  const map = {
    "Exceeds Expectations":    { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
    "Meets Expectations":      { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe" },
    "Needs Minor Calibration": { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
    "Needs Remediation":       { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
    "Excellent":               { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
    "Satisfactory":            { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe" },
    "Needs Improvement":       { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
    "Unsatisfactory":          { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
  };
  const s = map[rating] || map["Satisfactory"];
  return <span style={{ display: "inline-flex", alignItems: "center", padding: "5px 12px", borderRadius: 20, background: s.bg, color: s.color, border: `1px solid ${s.border}`, fontSize: 12, fontWeight: 700 }}>{rating}</span>;
}

function ScoreRing({ score, maxScore = 100 }) {
  const pct = Math.min(100, ((score || 0) / maxScore) * 100);
  const r = 34, circ = 2 * Math.PI * r, dash = (pct / 100) * circ;
  const color = pct >= 89 ? "#16a34a" : pct >= 74 ? "#8A5CF6" : pct >= 59 ? "#d97706" : "#dc2626";
  return (
    <div style={{ position: "relative", width: 88, height: 88, flexShrink: 0 }}>
      <svg width={88} height={88} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={44} cy={44} r={r} fill="none" stroke="#E5E7EB" strokeWidth={7} />
        <circle cx={44} cy={44} r={r} fill="none" stroke={color} strokeWidth={7} strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 19, fontWeight: 800, color: "#2B2F40", lineHeight: 1 }}>{score}</span>
        <span style={{ fontSize: 10, color: "#5E6573", fontWeight: 500 }}>/{maxScore}</span>
      </div>
    </div>
  );
}

function EmailPanel({ title, subtitle, tagColor, subject, body, formatBody }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ border: "1px solid #E5E7EB", borderRadius: 10, overflow: "hidden", marginBottom: 10 }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "13px 16px", background: "#F9FAFB", cursor: "pointer", userSelect: "none" }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: tagColor, flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#2B2F40" }}>{title}</div>
          <div style={{ fontSize: 11, color: "#5E6573", marginTop: 1 }}>{subtitle}</div>
        </div>
        <span style={{ fontSize: 16, color: "#9CA3AF", transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>›</span>
      </div>
      {open && (
        <div style={{ padding: "14px 16px", background: "#fff", borderTop: "1px solid #E5E7EB" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573", marginBottom: 4 }}>Subject</div>
          <div style={{ fontSize: 13, color: "#2B2F40", fontWeight: 500, marginBottom: 12 }}>{subject}</div>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573", marginBottom: 4 }}>Body</div>
          {formatBody && body ? (
            <div style={{ background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 10, padding: "12px 14px", maxHeight: 400, overflowY: "auto", marginBottom: 10 }}>
              <ReportRenderer text={body} />
            </div>
          ) : (
            <pre style={{ fontSize: 12, color: "#5E6573", lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word", background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 10, padding: "12px 14px", fontFamily: "inherit", maxHeight: 300, overflowY: "auto", marginBottom: 10 }}>{body}</pre>
          )}
          <button onClick={() => { navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
            style={{ padding: "8px 16px", background: copied ? "#8A5CF6" : "#fff", border: "1.5px solid #8A5CF6", borderRadius: 10, color: copied ? "#fff" : "#8A5CF6", fontSize: 12, fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>
            {copied ? "Copied!" : "Copy email"}
          </button>
        </div>
      )}
    </div>
  );
}

const inputBase = { width: "100%", padding: "10px 14px", border: "1.5px solid #E5E7EB", borderRadius: 10, fontSize: 13, color: "#2B2F40", background: "#fff", outline: "none", fontFamily: "inherit", transition: "border-color 0.15s, box-shadow 0.15s" };

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function CARSGrader() {
  // Form
  const [form, setForm] = useState({
    studentName: "", tutorName: "", tutorEmail: "",
    sessionDate: new Date().toISOString().split("T")[0],
    courseType: "515", sessionNumber: "1", transcript: "", studentDoc: "", studySchedule: "", fathomNotes: "",
    sopStudyScheduleUrl: "", sopStudySchedule: "no", sopQuestionPacks: "no", sopFullLengthExams: "no",
  });
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  // Grading
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [emails, setEmails] = useState(null);
  const [managementEmailSent, setManagementEmailSent] = useState(false);
  const [managementEmailError, setManagementEmailError] = useState(null);
  const [score, setScore] = useState(null);
  const [rating, setRating] = useState(null);
  const [gradeError, setGradeError] = useState(null);
  const reportRef = useRef(null);

  // Build a styled HTML email from the management summary + full grading report + draft tutor email at bottom
  const buildHtmlEmail = (summaryText, reportText, sessionMeta, tutorEmailBody) => {
    const esc = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    // Use only triage + summary (strip draft tutor email if present)
    let triageSummaryText = summaryText || "";
    if (tutorEmailBody) {
      const divider = triageSummaryText.match(/\n[-─━─]{10,}\s*\n|\n---\s*\n/);
      if (divider) triageSummaryText = triageSummaryText.slice(0, divider.index).trim();
      else {
        const hiMatch = triageSummaryText.search(/\n(Hi |Dear )[A-Za-z]/);
        if (hiMatch > 0) triageSummaryText = triageSummaryText.slice(0, hiMatch).trim();
      }
    }

    const renderTriageSummary = (text) => {
      const lines = (text || "").split("\n");
      const parts = [];
      let i = 0;
      const blockStyle = "background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:16px 20px;margin:10px 0";
      const labelStyle = "font-weight:700;color:#92400e;font-size:12px;margin-right:8px";
      while (i < lines.length) {
        const line = lines[i];
        const t = line.trim();
        if (/^[━─\-]{5,}$/.test(t)) { i++; continue; }
        if (/^TRIAGE SUMMARY$/i.test(t)) {
          parts.push(`<div style="font-size:12px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#b45309;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #fde68a">TRIAGE SUMMARY</div>`);
          i++; continue;
        }
        if (/^Tutor:/.test(t) && (t.includes("|") || t.includes("Student"))) {
          parts.push(`<p style="color:#5E6573;font-size:13px;margin:6px 0;line-height:1.6">${esc(t)}</p>`);
          i++; continue;
        }
        if (/^Score:\s*.+\|\s*Rating:/i.test(t)) {
          const scoreMatch = t.match(/Score:\s*(\d+)\/(\d+)\s*\|\s*Rating:\s*(.+)/i);
          const scoreNum = scoreMatch ? parseInt(scoreMatch[1], 10) : null;
          const scoreMax = scoreMatch ? parseInt(scoreMatch[2], 10) : 100;
          const scorePctLocal = scoreNum != null ? (scoreNum / scoreMax) * 100 : 0;
          const scoreColor = scoreNum != null ? (scorePctLocal >= 89 ? "#16a34a" : scorePctLocal >= 74 ? "#8A5CF6" : scorePctLocal >= 59 ? "#d97706" : "#dc2626") : "#5E6573";
          parts.push(`<p style="margin:10px 0 6px;font-size:13px"><span style="${labelStyle}">Score:</span><span style="font-weight:700;color:${scoreColor};margin-right:12px">${scoreMatch ? scoreMatch[1] + "/" + scoreMatch[2] : ""}</span><span style="${labelStyle}">Rating:</span><span style="color:#2B2F40">${scoreMatch ? esc(scoreMatch[3].trim()) : esc(t)}</span></p>`);
          i++; continue;
        }
        if (/^Action Required:/i.test(t)) {
          const action = t.replace(/^Action Required:\s*/i, "").trim();
          const actionColor = /YES|immediate|Remediation/i.test(action) ? "#dc2626" : /MONITOR|Monitor/i.test(action) ? "#d97706" : "#16a34a";
          parts.push(`<p style="margin:8px 0 14px;font-size:13px"><span style="${labelStyle}">Action Required:</span><span style="font-weight:700;color:${actionColor}">${esc(action)}</span></p>`);
          i++; continue;
        }
        if (/^SCORE BAND GUIDE$/i.test(t)) {
          parts.push(`<div style="font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#92400e;margin:16px 0 8px">Score band guide</div>`);
          parts.push(`<table style="width:100%;border-collapse:collapse;font-size:12px;color:#5E6573;margin-bottom:12px">`);
          i++;
          for (let r = 0; r < 4 && i < lines.length; r++, i++) {
            const row = lines[i].trim();
            if (!row) break;
            const byArrow = row.split(/\s*[→]\s*/).map(c => c.trim());
            const band = byArrow[0] || row.slice(0, 15);
            const desc = (byArrow.slice(1).join(" → ") || row).split(/\s*[—–-]\s*/).map(c => c.trim()).join(" — ") || row;
            parts.push(`<tr><td style="padding:4px 8px 4px 0;font-weight:600;color:#2B2F40;width:90px">${esc(band)}</td><td style="padding:4px 0">${esc(desc)}</td></tr>`);
          }
          parts.push("</table>");
          continue;
        }
        if (!t) {
          parts.push('<div style="height:8px"></div>');
          i++; continue;
        }
        if (t.startsWith("JW QA System") || t.startsWith("Sign:")) { i++; continue; }
        parts.push(`<p style="color:#5E6573;font-size:13px;line-height:1.7;margin:8px 0">${esc(t)}</p>`);
        i++;
      }
      return parts.join("");
    };

    const renderReport = (text) => {
      const lines = (text || "").split("\n");
      const parts = [];
      let i = 0;
      while (i < lines.length) {
        const line = lines[i];
        if (line.startsWith("## ")) {
          parts.push(`<h2 style="font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#8A5CF6;border-bottom:1px solid #EDE9FE;padding-bottom:8px;margin:28px 0 12px">${esc(line.replace("## ", ""))}</h2>`);
        } else if (line.startsWith("### ")) {
          parts.push(`<h3 style="font-size:15px;font-weight:600;color:#2B2F40;margin:18px 0 6px">${esc(line.replace("### ", ""))}</h3>`);
        } else if (isReportMainSection(line)) {
          const clean = esc(line.replace(/\*\*/g, "").trim());
          parts.push(`<p style="font-size:13px;font-weight:700;color:#2B2F40;margin-top:24px;margin-bottom:10px">${clean}</p>`);
        } else if (isReportCategoryLine(line)) {
          const content = esc(line).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
          parts.push(`<p style="font-size:13px;font-weight:700;color:#2B2F40;margin-top:14px;margin-bottom:6px;padding-left:16px">${content}</p>`);
        } else if (isReportSubsection(line)) {
          const clean = esc(line.replace(/\*\*/g, "").trim());
          parts.push(`<p style="font-size:13px;font-weight:700;color:#2B2F40;margin-top:12px;margin-bottom:6px;padding-left:12px">${clean}</p>`);
        } else if (line.startsWith("| ")) {
          const tLines = [];
          while (i < lines.length && lines[i].startsWith("|")) { tLines.push(lines[i]); i++; }
          const rows = tLines.filter(l => !/^\|[-:\s|]+\|$/.test(l));
          let table = '<table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #E5E7EB;border-radius:8px;margin:12px 0">';
          rows.forEach((row, ri) => {
            const cells = row.split("|").slice(1, -1);
            const isH = ri === 0;
            table += '<tr style="border-bottom:1px solid #E5E7EB">';
            cells.forEach(cell => {
              const clean = esc(cell.trim().replace(/\*\*/g, ""));
              table += isH
                ? `<th style="text-align:left;padding:8px 12px;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#5E6573;background:#F9FAFB;border-bottom:2px solid #EDE9FE">${clean}</th>`
                : `<td style="padding:8px 12px;color:#2B2F40;background:${ri % 2 === 0 ? "#fff" : "#FAFAFF"}">${clean}</td>`;
            });
            table += "</tr>";
          });
          table += "</table>";
          parts.push(table);
          continue;
        } else if (/^\d+\.\s/.test(line)) {
          const content = esc(line.replace(/^\d+\.\s/, "")).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
          const num = line.match(/^(\d+)\./)[1];
          parts.push(`<p style="margin:8px 0;padding-left:12px;color:#5E6573;font-size:13px;line-height:1.65"><span style="color:#8A5CF6;font-weight:700;margin-right:8px">${num}.</span>${content}</p>`);
        } else if (line.startsWith("- ")) {
          const content = esc(line.replace(/^-\s/, "")).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
          parts.push(`<p style="margin:6px 0;padding-left:12px;color:#5E6573;font-size:13px;line-height:1.65"><span style="color:#8A5CF6;margin-right:8px">●</span>${content}</p>`);
        } else if (line.startsWith("**") && line.endsWith("**")) {
          parts.push(`<p style="font-weight:700;color:#2B2F40;margin:12px 0 6px;padding-left:12px;font-size:13px">${esc(line.replace(/\*\*/g, ""))}</p>`);
        } else if (line === "---") {
          parts.push('<hr style="border:none;border-top:1px solid #E5E7EB;margin:20px 0">');
        } else if (!line.trim()) {
          parts.push('<div style="height:8px"></div>');
        } else {
          const content = esc(line).replace(/\*\*([^*]+)\*\*/g, "<strong style='color:#2B2F40'>$1</strong>");
          parts.push(`<p style="color:#5E6573;font-size:13px;line-height:1.7;margin:6px 0;padding-left:12px">${content}</p>`);
        }
        i++;
      }
      return parts.join("\n");
    };

    const is135 = sessionMeta.courseType && sessionMeta.courseType !== "CARS Strategy";
    const maxPts = is135 ? 135 : 100;
    let scoreNum = sessionMeta.score != null && sessionMeta.score !== "" ? Number(sessionMeta.score) : null;
    if (scoreNum == null || Number.isNaN(scoreNum)) {
      const reportScorePatterns = is135 ? [
        /\*\*TOTAL\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*135\*\*/i,
        /TOTAL[^|]*\|\s*(\d+)\s*\|\s*135/i,
        /Score[^0-9]*(\d+)\s*\/\s*135/i,
        /Score[^0-9]*(\d+)\s*\/\s*100/i,
      ] : [
        /Scaled Score[^:*\n]*:?\*?\s*(\d+)\s*\/\s*100/i,
        /\*\*Scaled Score\*\*:\s*(\d+)/i,
        /FINAL SCORE[:\s]+(\d+)\s*[\/\-]\s*100/i,
        /(\d+)\s*\/\s*100\s*[—\-]\s*(?:Exceeds|Meets|Needs)/i,
        /\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*100\*\*/i,
        /Score[^0-9]*(\d+)\s*\/\s*100/i,
      ];
      for (const re of reportScorePatterns) {
        const m = (reportText || "").match(re);
        if (m) {
          const n = parseInt(m[1], 10);
          if (n >= 0 && n <= maxPts) {
            scoreNum = n;
            break;
          }
        }
      }
    }
    const scoreDisplay = scoreNum != null && !Number.isNaN(scoreNum) ? String(scoreNum) : "—";
    const scorePct = scoreNum != null && !Number.isNaN(scoreNum) ? (scoreNum / maxPts) * 100 : 0;
    const scoreColor = scoreNum != null && !Number.isNaN(scoreNum)
      ? (scorePct >= 89 ? "#16a34a" : scorePct >= 74 ? "#8A5CF6" : scorePct >= 59 ? "#d97706" : "#dc2626")
      : "#9CA3AF";
    const ratingColors = {
      "Exceeds Expectations":    { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
      "Meets Expectations":      { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe" },
      "Needs Minor Calibration": { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
      "Needs Remediation":       { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
      "Excellent":               { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
      "Satisfactory":            { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe" },
      "Needs Improvement":       { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
      "Unsatisfactory":          { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
    };
    const rc = ratingColors[sessionMeta.rating] || ratingColors["Satisfactory"];

    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif">
<div style="max-width:680px;margin:0 auto;padding:24px 16px">

<!-- Header -->
<div style="background:linear-gradient(135deg,#8A5CF6 0%,#B88AFF 100%);border-radius:14px 14px 0 0;padding:24px 28px;text-align:center">
  <div style="display:inline-block;background:rgba(255,255,255,0.2);border-radius:8px;padding:4px 12px;margin-bottom:10px">
    <span style="color:#fff;font-size:12px;font-weight:800;letter-spacing:0.1em">JW SESSION GRADER</span>
  </div>
  <h1 style="color:#fff;font-size:20px;font-weight:700;margin:8px 0 4px">Session Grading Report</h1>
  <p style="color:rgba(255,255,255,0.8);font-size:13px;margin:0">${esc(sessionMeta.tutorName)} · ${esc(sessionMeta.studentName)} · Session ${esc(sessionMeta.sessionNumber)} · ${esc(sessionMeta.sessionDate)}</p>
</div>

<!-- Score card -->
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 28px;display:flex">
  <table style="width:100%"><tr>
    <td style="width:100px;text-align:center;vertical-align:middle">
      <div style="display:inline-block;width:80px;height:80px;border-radius:50%;border:6px solid ${scoreColor};text-align:center;line-height:68px">
        <span style="font-size:24px;font-weight:800;color:#2B2F40">${scoreDisplay}</span><span style="font-size:11px;color:#5E6573">/${maxPts}</span>
      </div>
    </td>
    <td style="vertical-align:middle;padding-left:18px">
      ${sessionMeta.rating ? `<span style="display:inline-block;padding:5px 14px;border-radius:20px;background:${rc.bg};color:${rc.color};border:1px solid ${rc.border};font-size:12px;font-weight:700;margin-bottom:8px">${esc(sessionMeta.rating)}</span><br>` : ""}
      <span style="font-size:12px;color:#5E6573">${esc(sessionMeta.courseType)} · ${esc(sessionMeta.tutorEmail || "")}</span>
    </td>
  </tr></table>
</div>

<!-- Triage summary (styled) -->
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 28px">
  <h2 style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#f59e0b;margin:0 0 14px;border-bottom:1px solid #fde68a;padding-bottom:8px">Triage Summary</h2>
  <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:18px 20px">
    ${renderTriageSummary(triageSummaryText)}
  </div>
</div>

<!-- Full grading report -->
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 28px">
  <h2 style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#8A5CF6;margin:0 0 14px;border-bottom:1px solid #EDE9FE;padding-bottom:8px">Full Grading Report</h2>
  ${renderReport(reportText)}
</div>

<!-- Draft tutor email (at bottom) -->
${tutorEmailBody ? `
<div style="background:#fff;border:1px solid #E5E7EB;border-top:none;padding:24px 28px">
  <h2 style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#8A5CF6;margin:0 0 14px;border-bottom:1px solid #EDE9FE;padding-bottom:8px">Draft Tutor Email</h2>
  <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;padding:18px 20px;font-size:13px;color:#2B2F40;line-height:1.7;white-space:pre-wrap;word-break:break-word">${esc(tutorEmailBody)}</div>
</div>
` : ""}

<!-- Score bands legend -->
<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:0 0 14px 14px;padding:14px 18px;margin-top:0;text-align:center">
  <span style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#5E6573">Score bands: </span>
  ${is135 ? `
  <span style="padding:3px 8px;border-radius:6px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:11px;color:#16a34a;font-weight:600">120–135 Excellent</span>
  <span style="padding:3px 8px;border-radius:6px;background:#eff6ff;border:1px solid #bfdbfe;font-size:11px;color:#2563eb;font-weight:600;margin-left:4px">100–119 Satisfactory</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fffbeb;border:1px solid #fde68a;font-size:11px;color:#d97706;font-weight:600;margin-left:4px">80–99 Needs Improvement</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fef2f2;border:1px solid #fecaca;font-size:11px;color:#dc2626;font-weight:600;margin-left:4px">&lt;80 Unsatisfactory</span>
  ` : `
  <span style="padding:3px 8px;border-radius:6px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:11px;color:#16a34a;font-weight:600">90–100 Exceeds</span>
  <span style="padding:3px 8px;border-radius:6px;background:#eff6ff;border:1px solid #bfdbfe;font-size:11px;color:#2563eb;font-weight:600;margin-left:4px">75–89 Meets</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fffbeb;border:1px solid #fde68a;font-size:11px;color:#d97706;font-weight:600;margin-left:4px">60–74 Coach</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fef2f2;border:1px solid #fecaca;font-size:11px;color:#dc2626;font-weight:600;margin-left:4px">&lt;60 Remediate</span>
  `}
</div>

<p style="text-align:center;font-size:11px;color:#9CA3AF;margin-top:18px">Sent by JW Session Grader · Internal QA Tool</p>
</div>
</body></html>`;
  };

  // ── Claude calls (via server proxy so API key stays server-side) ─────────────
  const callClaude = async (system, msg) => {
    const res = await fetch("/api/claude", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system, messages: [{ role: "user", content: msg }] }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Claude API error");
    return data.content || "";
  };

  const handleGrade = async () => {
    if (!form.transcript.trim() || !form.studentDoc.trim()) {
      setGradeError("Please provide both the session transcript and student notes document."); return;
    }
    setGradeError(null); setReport(null); setEmails(null); setScore(null); setRating(null); setManagementEmailSent(false); setManagementEmailError(null); setLoading(true);
    try {
      const gradingPrompt = (form.courseType === "cars") ? GRADING_PROMPT : ORIGINAL_GRADING_PROMPT;
      const sopVerification = `\n\nSOP VERIFICATION (manual input — third source of truth):\n- Study schedule provided in Google Sheet: ${form.sopStudySchedule.toUpperCase()}${form.sopStudyScheduleUrl ? ` (URL: ${form.sopStudyScheduleUrl})` : ""}\n- AAMC question packs assigned: ${form.sopQuestionPacks.toUpperCase()}\n- Ten full-length exams assigned: ${form.sopFullLengthExams.toUpperCase()}\n\nSOP VERIFICATION RULES:\n- YES = full credit for that SOP sub-item\n- PARTIAL = 50% credit for that SOP sub-item\n- NO = 0 points for that SOP sub-item UNLESS the transcript or student notes confirm otherwise (other sources can override a "No")\n- These manual inputs are a fail-safe — treat them as a third source of truth alongside transcript and student notes`;
      const gradeText = await callClaude(gradingPrompt,
        `COURSE TYPE: ${form.courseType === "515" ? "515+ Course" : form.courseType === "intensive" ? "Intensive" : "CARS Strategy"}\nSTUDENT: ${form.studentName||"Not provided"}\nTUTOR: ${form.tutorName||"Not provided"}\nSESSION: ${form.sessionNumber}\nDATE: ${form.sessionDate}\n\nTRANSCRIPT:\n${form.transcript}\n\nSTUDENT NOTES:\n${form.studentDoc}\n\nSTUDY SCHEDULE (reference only):\n${form.studySchedule||"Not provided"}\n\nFATHOM NOTES / SUMMARY (if provided):\n${form.fathomNotes||"Not provided"}${sopVerification}`
      );
      setReport(gradeText);

      let ps = null;
      const isCars = form.courseType === "cars";
      const scorePatterns = isCars ? [
        /Scaled Score[^:*\n]*:?\*?\s*(\d+)\s*\/\s*100/i,
        /\*\*Scaled Score\*\*:\s*(\d+)/i,
        /FINAL SCORE[:\s]+(\d+)\s*[\/\-]\s*100/i,
        /(\d+)\s*\/\s*100\s*[—\-]\s*(?:Exceeds|Meets|Needs)/i,
        /\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*100\*\*/i,
        /Score[^0-9]*(\d+)\s*\/\s*100/i,
      ] : [
        /\*\*TOTAL\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*135\*\*/i,
        /TOTAL[^|]*\|\s*(\d+)\s*\|\s*135/i,
        /\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*135\*\*/i,
        /Score[^0-9]*(\d+)\s*\/\s*135/i,
        /Scaled Score[^:*\n]*:?\*?\s*(\d+)\s*\/\s*100/i,
        /Score[^0-9]*(\d+)\s*\/\s*100/i,
      ];
      const maxScore = isCars ? 100 : 135;
      for (const re of scorePatterns) {
        const sm = gradeText.match(re);
        if (sm) {
          ps = parseInt(sm[1], 10);
          if (ps >= 0 && ps <= maxScore) break;
        }
      }
      if (ps !== null) setScore(ps);

      let pr = null;
      const rm = gradeText.match(/Overall (?:Assessment|Rating)[^|]*\|[^|]*\|\s*([^\n|]+)/i) || gradeText.match(/Overall Assessment:\*?\*?\s*([^\n]+)/i);
      if (rm) {
        const r = rm[1].trim().replace(/\*/g, "");
        if (isCars) {
          pr = r.includes("Exceeds") ? "Exceeds Expectations" : r.includes("Meets") ? "Meets Expectations" : r.includes("Minor") ? "Needs Minor Calibration" : "Needs Remediation";
        } else {
          pr = r.includes("Excellent") ? "Excellent" : r.includes("Satisfactory") ? "Satisfactory" : r.includes("Needs Improvement") || r.includes("Improvement") ? "Needs Improvement" : "Unsatisfactory";
        }
        setRating(pr);
      }

      const emailText = await callClaude(EMAIL_PROMPT,
        `STUDENT: ${form.studentName||"Not provided"}\nTUTOR: ${form.tutorName||"Not provided"}\nTUTOR EMAIL: ${form.tutorEmail||"Not provided"}\nSESSION: ${form.sessionNumber}\nDATE: ${form.sessionDate}\nSCORE: ${ps}/${maxScore}\nRATING: ${pr}\n\nGRADING REPORT:\n${gradeText}`
      );
      let parsed = null;
      try {
        parsed = JSON.parse(emailText.replace(/```json|```/g, "").trim());
        setEmails(parsed);
      } catch {
        parsed = { tutorEmail: { subject: `Session ${form.sessionNumber} Grading Report`, body: emailText }, managementEmail: { subject: `Session ${form.sessionNumber} QA Report`, body: emailText } };
        setEmails(parsed);
      }
      // Send management email to directors via /api/send-email
      if (parsed?.managementEmail) {
        try {
          const htmlContent = buildHtmlEmail(
            parsed.managementEmail.body,
            gradeText,
            { tutorName: form.tutorName, studentName: form.studentName, sessionNumber: form.sessionNumber, sessionDate: form.sessionDate, score: ps, rating: pr, courseType: form.courseType === "cars" ? "CARS Strategy" : form.courseType === "intensive" ? "Intensive" : "515+", tutorEmail: form.tutorEmail },
            parsed.tutorEmail?.body
          );
          const sendRes = await fetch("/api/send-email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              subject: parsed.managementEmail.subject,
              body: parsed.managementEmail.body,
              html: htmlContent,
            }),
          });
          const sendJson = await sendRes.json();
          if (sendJson.success) {
            setManagementEmailSent(true);
          } else {
            setManagementEmailError(sendJson.error || "Send failed");
          }
        } catch (emailErr) {
          setManagementEmailError(emailErr.message);
        }
      }
      // Store transcript + grading outcome for 3-day director digest
      try {
        await fetch("/api/record-session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tutor_name: form.tutorName || null,
            tutor_email: form.tutorEmail || null,
            student_name: form.studentName || null,
            session_date: form.sessionDate || null,
            session_number: form.sessionNumber || null,
            course_type: form.courseType || null,
            score: ps ?? null,
            rating: pr || null,
            report_text: gradeText || null,
            transcript_text: form.transcript || null,
            fathom_notes: form.fathomNotes || null,
            sop_study_schedule: form.sopStudySchedule || null,
            sop_study_schedule_url: form.sopStudyScheduleUrl || null,
            sop_question_packs: form.sopQuestionPacks || null,
            sop_full_length_exams: form.sopFullLengthExams || null,
            host_data: null,
          }),
        });
      } catch (_) { /* optional: session still recorded when Supabase is configured */ }
      setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
    } catch (e) { setGradeError(e.message); }
    finally { setLoading(false); }
  };

  // Inline form content (not a nested component) so inputs don't remount and lose focus on each keystroke
  const renderFormContent = () => (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        {[{ k: "studentName", l: "Student Name", t: "text", ph: "e.g. Jordan Kim" },
          { k: "tutorName",   l: "Tutor Name",   t: "text", ph: "e.g. Sarah Chen" },
          { k: "tutorEmail",  l: "Tutor Email",  t: "email", ph: "tutor@jackwestin.com" },
          { k: "sessionDate", l: "Session Date", t: "date", ph: "" },
        ].map(({ k, l, t, ph }) => (
          <div key={k} style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>{l}</label>
            <input type={t} placeholder={ph} value={form[k]} onChange={set(k)} style={inputBase} />
          </div>
        ))}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>Course type</label>
        <select value={form.courseType} onChange={set("courseType")} style={{ ...inputBase, cursor: "pointer", appearance: "none", backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%235E6573' stroke-width='2.5'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 13px center", paddingRight: 36 }}>
          <option value="515">515+ Course</option>
          <option value="intensive">Intensive</option>
          <option value="cars">CARS Strategy</option>
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>Session Number</label>
        <select value={form.sessionNumber} onChange={set("sessionNumber")} style={{ ...inputBase, cursor: "pointer", appearance: "none", backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%235E6573' stroke-width='2.5'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 13px center", paddingRight: 36 }}>
          <option value="1">Session 1 — Onboarding &amp; Plan Build</option>
          <option value="2">Session 2 — Adherence &amp; Adjustment</option>
          <option value="3">Session 3 — Timed Pressure &amp; Diagnostics</option>
        </select>
      </div>
      <div style={{ height: 1, background: "#E5E7EB", margin: "4px 0 16px" }} />

      {/* Transcript */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>Session Transcript <span style={{ color: "#dc2626" }}>*</span></label>
        <textarea rows={7} placeholder="Paste the full session transcript here…" value={form.transcript} onChange={set("transcript")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>
          Student Notes Document <span style={{ color: "#dc2626" }}>*</span>
          <span style={{ fontWeight: 400, color: "#5E6573", fontSize: 11, marginLeft: 8 }}>Primary artifact being graded</span>
        </label>
        <textarea rows={7} placeholder="Paste the Course Tutoring Notes Template contents…" value={form.studentDoc} onChange={set("studentDoc")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>
          Study Schedule
          <span style={{ fontWeight: 400, color: "#5E6573", fontSize: 11, marginLeft: 8 }}>Reference only — not graded</span>
        </label>
        <textarea rows={3} placeholder="Optional…" value={form.studySchedule} onChange={set("studySchedule")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 6 }}>
          Fathom notes / summary
          <span style={{ fontWeight: 400, color: "#5E6573", fontSize: 11, marginLeft: 8 }}>Optional — paste Fathom-generated summary or meeting notes</span>
        </label>
        <textarea rows={4} placeholder="Paste Fathom summary or meeting notes here (e.g. AI summary, action items)…" value={form.fathomNotes} onChange={set("fathomNotes")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      {/* SOP Verification */}
      <div style={{ height: 1, background: "#E5E7EB", margin: "4px 0 16px" }} />
      <div style={{ marginBottom: 18 }}>
        <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#8A5CF6", marginBottom: 14 }}>SOP Verification</p>
        <p style={{ fontSize: 12, color: "#5E6573", marginBottom: 16, lineHeight: 1.6 }}>Manual confirmation of key SOP items. These inputs act as a third source of truth alongside the transcript and student notes.</p>

        {/* Study Schedule */}
        <div style={{ marginBottom: 16, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 8 }}>Study schedule provided in a Google Sheet</label>
          <input type="url" placeholder="https://docs.google.com/spreadsheets/d/..." value={form.sopStudyScheduleUrl} onChange={set("sopStudyScheduleUrl")} style={{ ...inputBase, marginBottom: 10 }} />
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopStudySchedule: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopStudySchedule === val ? "#8A5CF6" : "#E5E7EB"}`, background: form.sopStudySchedule === val ? "#EDE9FE" : "#fff", color: form.sopStudySchedule === val ? "#8A5CF6" : "#5E6573", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* AAMC Question Packs */}
        <div style={{ marginBottom: 16, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 8 }}>Have the AAMC question packs been assigned?</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopQuestionPacks: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopQuestionPacks === val ? "#8A5CF6" : "#E5E7EB"}`, background: form.sopQuestionPacks === val ? "#EDE9FE" : "#fff", color: form.sopQuestionPacks === val ? "#8A5CF6" : "#5E6573", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Full-Length Exams */}
        <div style={{ marginBottom: 4, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#2B2F40", marginBottom: 8 }}>Have ten full-length exams been assigned?</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopFullLengthExams: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopFullLengthExams === val ? "#8A5CF6" : "#E5E7EB"}`, background: form.sopFullLengthExams === val ? "#EDE9FE" : "#fff", color: form.sopFullLengthExams === val ? "#8A5CF6" : "#5E6573", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>
      </div>

      {gradeError && <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#dc2626", fontSize: 13, marginBottom: 14 }}>{gradeError}</div>}

      <button onClick={handleGrade} disabled={loading} style={{ width: "100%", padding: "14px 24px", background: loading ? "#B88AFF" : "linear-gradient(135deg, #8A5CF6 0%, #B88AFF 100%)", color: "#fff", border: "none", borderRadius: 12, fontSize: 14, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 10, boxShadow: loading ? "none" : "0 4px 16px rgba(138,92,246,0.35)", transition: "all 0.15s" }}>
        {loading
          ? <><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2.5" style={{ animation: "spin 0.8s linear infinite", flexShrink: 0 }}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>Grading session + generating email drafts…</>
          : <>Grade this session <span style={{ marginLeft: 4 }}>→</span></>}
      </button>
    </>
  );

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #fff !important; }
        input:focus, textarea:focus, select:focus { border-color: #8A5CF6 !important; box-shadow: 0 0 0 3px rgba(138,92,246,0.12) !important; outline: none; }
        textarea { font-family: 'Inter', sans-serif; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      <div style={{ minHeight: "100vh", background: "#fff", fontFamily: "'Inter', sans-serif", paddingBottom: 80 }}>

        {/* Nav */}
        <nav style={{ background: "#fff", borderBottom: "1px solid #E5E7EB", padding: "0 24px", height: 56, display: "flex", alignItems: "center", position: "sticky", top: 0, zIndex: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg, #8A5CF6 0%, #B88AFF 100%)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ color: "#fff", fontSize: 11, fontWeight: 800 }}>JW</span>
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#2B2F40" }}>Session Grader</span>
            <span style={{ width: 1, height: 14, background: "#E5E7EB", margin: "0 6px" }} />
            <span style={{ fontSize: 12, color: "#5E6573" }}>Internal QA Tool</span>
          </div>
        </nav>

        <div style={{ maxWidth: 780, margin: "0 auto", padding: "40px 20px 0" }}>

          {/* Hero */}
          <div style={{ marginBottom: 32 }}>
            <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", color: "#5E6573", textTransform: "uppercase", marginBottom: 12 }}>515+ · Intensive · CARS</p>
            <h1 style={{ fontSize: "clamp(26px, 4vw, 38px)", fontWeight: 700, color: "#2B2F40", lineHeight: 1.2, letterSpacing: "-0.02em", marginBottom: 12 }}>Session grading, powered by AI.</h1>
            <p style={{ fontSize: 15, color: "#5E6573", lineHeight: 1.7, maxWidth: 560 }}>
              Grade 515+, Intensive, or CARS sessions. Paste transcript and student notes to generate grading reports and email drafts.
            </p>
          </div>

          {/* Session form */}
          <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E5E7EB", padding: "24px 24px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", animation: "fadeUp 0.2s ease" }}>
            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#5E6573", marginBottom: 16 }}>Session details</p>
            {renderFormContent()}
          </div>

          {/* ── RESULTS ── */}
          {report && (
            <div ref={reportRef} style={{ marginTop: 24, animation: "fadeUp 0.4s ease" }}>
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12, padding: "18px 22px", marginBottom: 10, display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                {score !== null && <ScoreRing score={score} maxScore={form.courseType === "cars" ? 100 : 135} />}
                <div style={{ flex: 1, minWidth: 180 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573", marginBottom: 6 }}>Grading complete</p>
                  <div style={{ marginBottom: 7 }}>{rating && <RatingBadge rating={rating} />}</div>
                  <p style={{ fontSize: 12, color: "#5E6573" }}>{[form.tutorName, form.studentName, `Session ${form.sessionNumber}`, form.sessionDate].filter(Boolean).join(" · ")}</p>
                </div>
                <button onClick={() => navigator.clipboard.writeText(report)} style={{ padding: "8px 16px", border: "1.5px solid #8A5CF6", borderRadius: 10, background: "#fff", color: "#8A5CF6", fontSize: 12, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>Copy report</button>
              </div>

              {/* Email status */}
              {managementEmailSent && (
                <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10, padding: "11px 16px", marginBottom: 10, fontSize: 13, color: "#065f46" }}>
                  Report emailed to directors (anastasia, carlb, Molly, adamrs)
                </div>
              )}
              {managementEmailError && (
                <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "11px 16px", marginBottom: 10, fontSize: 13, color: "#991b1b" }}>
                  Email send failed: {managementEmailError}
                </div>
              )}

              {/* Score bands */}
              <div style={{ background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 10, padding: "11px 16px", marginBottom: 10, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573" }}>Score bands</span>
                {(form.courseType === "cars"
                  ? [["90–100","#16a34a","#f0fdf4","#bbf7d0","Exceeds"],["75–89","#2563eb","#eff6ff","#bfdbfe","Meets"],["60–74","#d97706","#fffbeb","#fde68a","Coach"],["<60","#dc2626","#fef2f2","#fecaca","Remediate"]]
                  : [["120–135","#16a34a","#f0fdf4","#bbf7d0","Excellent"],["100–119","#2563eb","#eff6ff","#bfdbfe","Satisfactory"],["80–99","#d97706","#fffbeb","#fde68a","Needs Improvement"],["<80","#dc2626","#fef2f2","#fecaca","Unsatisfactory"]]
                ).map(([range,c,bg,b,l])=>(
                  <span key={range} style={{padding:"3px 10px",borderRadius:8,background:bg,border:`1px solid ${b}`,fontSize:11,color:c,fontWeight:600}}><strong>{range}</strong> — {l}</span>
                ))}
              </div>

              {/* Full grading report — first */}
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#5E6573", marginBottom: 8 }}>Full grading report</p>
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12, padding: "26px 26px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", marginBottom: 16 }}>
                <ReportRenderer text={report} />
              </div>

              {/* Email drafts — tutor draft (not sent) + management email (sent to directors) */}
              {emails && (
                <div style={{ marginBottom: 10 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#5E6573", marginBottom: 8 }}>Emails</p>
                  <EmailPanel title="Draft Tutor Email" subtitle={`To: ${form.tutorEmail || form.tutorName || "tutor"} · Detailed grading report (draft only — not sent)`} tagColor="#8A5CF6" subject={emails.tutorEmail?.subject} body={emails.tutorEmail?.body} formatBody />
                  <EmailPanel title="Management Report" subtitle={`To: Directors · ${managementEmailSent ? "Sent" : "Pending"}`} tagColor={managementEmailSent ? "#16a34a" : "#f59e0b"} subject={emails.managementEmail?.subject} body={emails.managementEmail?.body} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
