import { useState, useRef } from "react";

// ─── Grading system prompt ────────────────────────────────────────────────────
const GRADING_PROMPT = `You are the JW CARS Session Grader, an internal QA agent for Jack Westin MCAT CARS Strategy Course tutoring.

CORE GRADING RULES
1. Grade the NOTES primarily. Transcript reveals what SHOULD be documented and assesses live coaching quality.
2. Evidence must be explicit. No credit for implied content. Partial credit when partial documentation exists.
3. Score conservatively when uncertain.
4. AAMC DUAL-SOURCE RULE: For AAMC scheduling/sequencing, check BOTH the transcript AND the student notes document. If EITHER source confirms AAMC materials were assigned/scheduled/completed, award full credit. Only deduct if BOTH sources fail to confirm. The student notes document saying "yes" to assigning all AAMC documents is sufficient on its own.

SESSION 1 RUBRIC — Onboarding & Plan Build (100 pts documentation + 50 pts coaching = 150 total, scaled to 100)
PASS/FAIL GATES: Session Notes Template copied and completed | Strategy Portion completed (teach-back occurred) | Study Plan updated | Fathom summary forwarded (mark Unable to Verify)

A. Preparation & Planning Readiness — 20 pts
   20: Test date confirmed, baseline CARS score reviewed, JW mapping principles noted, below-average areas identified
   15: Most elements present  10: Test date/goals only  5: Mostly reactive  0: No prep

B. Study Plan Construction Quality — 30 pts
   30: 6+ FLs scheduled with dates, AAMC sequencing, weekly checklist, Week 1 daily tasks, HW Tracker link
   22: Strong plan  15: Exists but lacks specificity  8: General advice only  0: No plan

C. Personalization & Load Calibration — 15 pts
   15: Adapted to availability/timeline  11: Availability acknowledged  7: Some personalization  3: Constraints mentioned  0: None

D. Strategy Portion Execution — 25 pts
   25: Student taught back; per-paragraph feedback; 3+ questions; missed reasons identified; videos recommended
   19: Teach-back + some questions  12: Mostly tutor-led  6: Brief mention  0: No teach-back (auto 0)

E. Clarity & Student Buy-In — 10 pts
   10: Takeaways verbalized; next steps explicit; next session scheduled; HW Tracker explained
   7: Plan summarized  5: Clarity not verified  2: Unclear  0: None

SESSION 1 SOP CHECKLIST: Student Overview completed | Passage video takeaways | 6+ FL exam schedule | AAMC sequencing | Weekly checklist | Week 1 daily tasks | Strategy notes | 2+ video recs | HW Tracker link | Next session date | Fathom forwarded

SESSION 2 RUBRIC — Adherence & Adjustment (100+50=150, scaled to 100)
PASS/FAIL GATES: same as Session 1
A. Prep & Data Review — 15 pts  B. Accountability & Reflection — 25 pts  C. Plan Adjustment Quality — 20 pts  D. Time Management Coaching — 15 pts  E. Strategy Portion Execution — 25 pts
SESSION 2 SOP: HW Tracker status | Timed section reviewed | 5 reflection areas | Roadblocks noted | Updated schedule | Strategy notes | Next session | Fathom forwarded

SESSION 3 RUBRIC — Timed Pressure & Diagnostics (100+50=150, scaled to 100)
PASS/FAIL GATES: same as Session 1
A. Diagnostic Design Quality — 20 pts  B. Accountability Enforcement — 20 pts  C. Timing & Accuracy Analysis — 25 pts  D. Personalized Coaching Using Visuals — 15 pts  E. Strategy Portion Execution — 20 pts
SESSION 3 SOP: Timed section assigned+done | 5 reflection areas | Timing data | Per-passage insights | Personalized timing advice | Updated plan | Test-day strategy | Fathom forwarded

UNIVERSAL TEACHING QUALITY — from TRANSCRIPT (50 pts):
A. Approachability 10pts  B. CARS Passage Framing 15pts  C. CARS Question Approach 15pts  D. Student Metacognition 10pts
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
| Approachability | X/10 | [evidence] |
| CARS Passage Framing | X/15 | [evidence] |
| CARS Question Approach | X/15 | [evidence] |
| Student Metacognition | X/10 | [evidence] |
| **Subtotal** | **X/50** | |
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
| Teaching Quality | X | 50 |
| **TOTAL** | **X** | **150** |
**Scaled Score:** X/100
**Overall Assessment:** [rating]
**Summary:** [3-4 sentences]

Bands: 90-100=Exceeds, 75-89=Meets, 60-74=Needs Minor Calibration, <60=Needs Remediation. Any failed gate=Needs Remediation.`;

// 515+ Course & Intensive — original rubric (Tutoring Session Grading & Feedback SOP)
const ORIGINAL_GRADING_PROMPT = `You are the JW Session Grader for the 515+ MCAT Course and Intensive course. Grade using the standard tutoring session rubric (NOT the CARS-specific rubric).

UNIVERSAL RULES (all sessions)
- Grade the NOTES primarily; transcript shows what should be documented and session quality.
- Evidence must be explicit. No credit for implied content. Partial credit when partial documentation exists.
- Any category without concrete evidence loses 50% of its points.
- Strategy Portion receives 0 points if teach-back does not occur.
- Missing any Pass/Fail Gate → Needs Remediation regardless of score.
- AAMC DUAL-SOURCE RULE: For AAMC scheduling/deadlines, check BOTH the transcript AND the student notes document. If EITHER source confirms AAMC materials were assigned/scheduled/completed, award full credit. Only deduct if BOTH sources fail to confirm. The student notes document saying "yes" to assigning all AAMC documents is sufficient on its own.

PASS/FAIL GATES (missing any = Needs Remediation):
Session Notes Template copied and completed | Strategy Portion completed (teach-back occurred) | Study Plan updated | Fathom summary forwarded to Molly Kielty and Anastasia (mark Unable to Verify if not evidenced)

SESSION 1 — Onboarding & Plan Build (100 pts rubric + 50 pts teaching = 150, scaled to 100)
A. Preparation & Planning Readiness — 20 pts: Baseline reviewed, test date framed, topic gaps identified
B. Study Plan Construction Quality — 30 pts: Exam schedule, AAMC deadlines, weekly checklist, daily tasks for Week 1
C. Personalization & Load Calibration — 15 pts: Plan matches availability and constraints
D. Strategy Portion Execution — 25 pts: Teach-back, feedback, tough questions, plan updates
E. Clarity & Student Buy-In — 10 pts: Student understands plan and next steps

Required in Session 1 notes: Exam schedule | AAMC deadlines | Below-average topics (excluding course-covered) | Weekly checklist | Daily tasks Week 1 | Strategy portion notes | Tentative next session date

SESSION 2 — Adherence & Adjustment (100 pts + 50 teaching = 150, scaled to 100)
A. Prep & Data Review — 15 pts: Checklist reviewed prior to meeting
B. Accountability & Reflection Execution — 25 pts: Reflection survey used to diagnose roadblocks
C. Plan Adjustment Quality — 20 pts: Adjustments specific and constraint-aware
D. Time Management Coaching — 15 pts: Concrete pacing or scheduling changes
E. Strategy Portion Execution — 25 pts: Teach-back, feedback, assignments added

Required in Session 2 notes: Weekly checklist completion status | Roadblocks + interventions | Updated study schedule | Strategy notes | Next session tentatively scheduled

SESSION 3 — Timed Pressure & Diagnostics (100 pts + 50 teaching = 150, scaled to 100)
A. Diagnostic Design Quality — 20 pts: Weakest section selected, instructions clear
B. Accountability Enforcement — 20 pts: Completion + review + reflections enforced
C. Timing & Accuracy Analysis — 25 pts: Data entered, insights specific
D. Personalized Coaching Using Visuals — 15 pts: Visual timing guidance + rules
E. Strategy Portion Execution — 20 pts: Teach-back + targeted practice assigned

Required in Session 3 notes: Reflection responses | Timing and accuracy insights | Personalized timing advice | Updated Study Plan to test day

TEACHING & LEARNING (50 pts, from transcript): Approachability 10 | Science Passage Framing 15 | CARS Passage Framing 15 | Student Metacognition 10

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
- Fathom Forwarded: [Unable to Verify / PASS / FAIL]

**Top 3 Fixes:**
1. [fix]
2. [fix]
3. [fix]

---
## SECTION 2: CATEGORY SCORES
### A. [Name] — [score]/[max] pts
**Justification:** [evidence-based observation]
**Next step:** [actionable next step]
**Missing from Notes:**
- [bullets]
[repeat B–E]

---
## SECTION 3: SOP COMPLIANCE CHECKLIST
| SOP Item | Status | Evidence |
|----------|--------|----------|
[all items]
**Compliance Summary:** [X] fully met, [Y] partial, [Z] missing

---
## SECTION 4: TRANSCRIPT COACHING QUALITY (Teaching & Learning)
| Behavior | Score | Observation |
|----------|-------|-------------|
| Approachability | X/10 | [evidence] |
| Science Passage Framing | X/15 | [evidence] |
| CARS Passage Framing | X/15 | [evidence] |
| Student Metacognition | X/10 | [evidence] |
| **Subtotal** | **X/50** | |

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
[repeat B–E]
| Teaching & Learning | X | 50 |
| **TOTAL** | **X** | **150** |
**Scaled Score:** X/100
**Overall Assessment:** [rating]
**Summary:** [3-4 sentences]

Bands: 90-100=Exceeds, 75-89=Meets, 60-74=Needs Minor Calibration, <60=Needs Remediation. Any failed gate=Needs Remediation.`;

const EMAIL_PROMPT = `You are a professional email writer for Jack Westin's MCAT tutoring program. Given a grading report, produce TWO emails as JSON only — no markdown fences, no preamble:
{"tutorEmail":{"subject":"...","body":"..."},"managementEmail":{"subject":"...","body":"..."}}

TUTOR EMAIL: Subject "Session [N] Grading Report — [Student Name]". Address tutor by first name. Open with 1-2 sentences on what they did well. Then full graded report in plain text: SESSION [N] GRADING REPORT / Student/Tutor/Date / QUICK VERDICT (rating, score, risk, top 3 fixes) / CATEGORY SCORES A-E (score, justification, missing items) / SOP CHECKLIST / COACHING QUALITY / TUTOR FEEDBACK (what went well + areas for improvement) / FINAL SCORE. Close warmly. Sign: "The JW QA Team"

MANAGEMENT EMAIL: Subject "Session [N] QA — [Tutor Name] | [Score]/100 | [Rating]". Open with TRIAGE block:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIAGE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tutor: [name] | Student: [name] | Session: [N] | Date: [date]
Score: [X]/100 | Rating: [rating]
Action Required: [YES — immediate follow-up / MONITOR — check next session / NONE — on track]

SCORE BAND GUIDE
90-100 → Exceeds Expectations     — No action needed
75-89  → Meets Expectations       — Monitor progress
60-74  → Needs Minor Calibration  — Provide targeted coaching
<60    → Needs Remediation        — Immediate manager follow-up required
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
  };
  const s = map[rating] || map["Meets Expectations"];
  return <span style={{ display: "inline-flex", alignItems: "center", padding: "5px 12px", borderRadius: 20, background: s.bg, color: s.color, border: `1px solid ${s.border}`, fontSize: 12, fontWeight: 700 }}>{rating}</span>;
}

function ScoreRing({ score }) {
  const pct = Math.min(100, score || 0);
  const r = 34, circ = 2 * Math.PI * r, dash = (pct / 100) * circ;
  const color = pct >= 90 ? "#16a34a" : pct >= 75 ? "#8A5CF6" : pct >= 60 ? "#d97706" : "#dc2626";
  return (
    <div style={{ position: "relative", width: 88, height: 88, flexShrink: 0 }}>
      <svg width={88} height={88} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={44} cy={44} r={r} fill="none" stroke="#E5E7EB" strokeWidth={7} />
        <circle cx={44} cy={44} r={r} fill="none" stroke={color} strokeWidth={7} strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 19, fontWeight: 800, color: "#2B2F40", lineHeight: 1 }}>{score}</span>
        <span style={{ fontSize: 10, color: "#5E6573", fontWeight: 500 }}>/100</span>
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
  });
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  // Grading
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [emails, setEmails] = useState(null);
  const [managementEmailSent, setManagementEmailSent] = useState(null);
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
          const scoreMatch = t.match(/Score:\s*(\d+)\/100\s*\|\s*Rating:\s*(.+)/i);
          const scoreNum = scoreMatch ? parseInt(scoreMatch[1], 10) : null;
          const scoreColor = scoreNum != null ? (scoreNum >= 90 ? "#16a34a" : scoreNum >= 75 ? "#8A5CF6" : scoreNum >= 60 ? "#d97706" : "#dc2626") : "#5E6573";
          parts.push(`<p style="margin:10px 0 6px;font-size:13px"><span style="${labelStyle}">Score:</span><span style="font-weight:700;color:${scoreColor};margin-right:12px">${scoreMatch ? scoreMatch[1] + "/100" : ""}</span><span style="${labelStyle}">Rating:</span><span style="color:#2B2F40">${scoreMatch ? esc(scoreMatch[2].trim()) : esc(t)}</span></p>`);
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

    let scoreNum = sessionMeta.score != null && sessionMeta.score !== "" ? Number(sessionMeta.score) : null;
    if (scoreNum == null || Number.isNaN(scoreNum)) {
      const reportScorePatterns = [
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
          if (n >= 0 && n <= 100) {
            scoreNum = n;
            break;
          }
        }
      }
    }
    const scoreDisplay = scoreNum != null && !Number.isNaN(scoreNum) ? String(scoreNum) : "—";
    const scoreColor = scoreNum != null && !Number.isNaN(scoreNum)
      ? (scoreNum >= 90 ? "#16a34a" : scoreNum >= 75 ? "#8A5CF6" : scoreNum >= 60 ? "#d97706" : "#dc2626")
      : "#9CA3AF";
    const ratingColors = {
      "Exceeds Expectations":    { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
      "Meets Expectations":      { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe" },
      "Needs Minor Calibration": { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
      "Needs Remediation":       { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
    };
    const rc = ratingColors[sessionMeta.rating] || ratingColors["Meets Expectations"];

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
        <span style="font-size:24px;font-weight:800;color:#2B2F40">${scoreDisplay}</span><span style="font-size:11px;color:#5E6573">/100</span>
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
  <span style="padding:3px 8px;border-radius:6px;background:#f0fdf4;border:1px solid #bbf7d0;font-size:11px;color:#16a34a;font-weight:600">90–100 Exceeds</span>
  <span style="padding:3px 8px;border-radius:6px;background:#eff6ff;border:1px solid #bfdbfe;font-size:11px;color:#2563eb;font-weight:600;margin-left:4px">75–89 Meets</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fffbeb;border:1px solid #fde68a;font-size:11px;color:#d97706;font-weight:600;margin-left:4px">60–74 Coach</span>
  <span style="padding:3px 8px;border-radius:6px;background:#fef2f2;border:1px solid #fecaca;font-size:11px;color:#dc2626;font-weight:600;margin-left:4px">&lt;60 Remediate</span>
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
    setGradeError(null); setReport(null); setEmails(null); setScore(null); setRating(null); setManagementEmailSent(null); setManagementEmailError(null); setLoading(true);
    try {
      const gradingPrompt = (form.courseType === "cars") ? GRADING_PROMPT : ORIGINAL_GRADING_PROMPT;
      const gradeText = await callClaude(gradingPrompt,
        `COURSE TYPE: ${form.courseType === "515" ? "515+ Course" : form.courseType === "intensive" ? "Intensive" : "CARS Strategy"}\nSTUDENT: ${form.studentName||"Not provided"}\nTUTOR: ${form.tutorName||"Not provided"}\nSESSION: ${form.sessionNumber}\nDATE: ${form.sessionDate}\n\nTRANSCRIPT:\n${form.transcript}\n\nSTUDENT NOTES:\n${form.studentDoc}\n\nSTUDY SCHEDULE (reference only):\n${form.studySchedule||"Not provided"}\n\nFATHOM NOTES / SUMMARY (if provided):\n${form.fathomNotes||"Not provided"}`
      );
      setReport(gradeText);

      let ps = null;
      const scorePatterns = [
        /Scaled Score[^:*\n]*:?\*?\s*(\d+)\s*\/\s*100/i,
        /\*\*Scaled Score\*\*:\s*(\d+)/i,
        /FINAL SCORE[:\s]+(\d+)\s*[\/\-]\s*100/i,
        /(\d+)\s*\/\s*100\s*[—\-]\s*(?:Exceeds|Meets|Needs)/i,
        /\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*100\*\*/i,
        /Score[^0-9]*(\d+)\s*\/\s*100/i,
      ];
      for (const re of scorePatterns) {
        const sm = gradeText.match(re);
        if (sm) {
          ps = parseInt(sm[1], 10);
          if (ps >= 0 && ps <= 100) break;
        }
      }
      if (ps !== null) setScore(ps);

      let pr = null;
      const rm = gradeText.match(/Overall (?:Assessment|Rating)[^|]*\|[^|]*\|\s*([^\n|]+)/i);
      if (rm) {
        const r = rm[1].trim().replace(/\*/g, "");
        pr = r.includes("Exceeds") ? "Exceeds Expectations" : r.includes("Meets") ? "Meets Expectations" : r.includes("Minor") ? "Needs Minor Calibration" : "Needs Remediation";
        setRating(pr);
      }

      const emailText = await callClaude(EMAIL_PROMPT,
        `STUDENT: ${form.studentName||"Not provided"}\nTUTOR: ${form.tutorName||"Not provided"}\nTUTOR EMAIL: ${form.tutorEmail||"Not provided"}\nSESSION: ${form.sessionNumber}\nDATE: ${form.sessionDate}\nSCORE: ${ps}/100\nRATING: ${pr}\n\nGRADING REPORT:\n${gradeText}`
      );
      let parsed = null;
      try {
        parsed = JSON.parse(emailText.replace(/```json|```/g, "").trim());
        setEmails(parsed);
      } catch {
        parsed = { tutorEmail: { subject: `Session ${form.sessionNumber} Grading Report`, body: emailText }, managementEmail: { subject: `Session ${form.sessionNumber} QA Report`, body: emailText } };
        setEmails(parsed);
      }
      if (parsed?.managementEmail?.subject && parsed?.managementEmail?.body) {
        const fullBody = parsed.managementEmail.body
          + "\n\n────────────────────────────────────────\nFULL GRADING REPORT\n────────────────────────────────────────\n\n"
          + gradeText;
        const htmlEmail = buildHtmlEmail(parsed.managementEmail.body, gradeText, {
          tutorName: form.tutorName || "—",
          tutorEmail: form.tutorEmail || "",
          studentName: form.studentName || "—",
          sessionNumber: form.sessionNumber || "—",
          sessionDate: form.sessionDate || "—",
          courseType: form.courseType === "515" ? "515+ Course" : form.courseType === "intensive" ? "Intensive" : "CARS Strategy",
          score: ps,
          rating: pr,
        }, parsed.tutorEmail?.body);
        try {
          const sendRes = await fetch("/api/send-email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ subject: parsed.managementEmail.subject, body: fullBody, html: htmlEmail }),
          });
          let sendData;
          try {
            sendData = await sendRes.json();
          } catch {
            setManagementEmailSent(false);
            setManagementEmailError(sendRes.status ? `${sendRes.status} ${sendRes.statusText} — invalid response` : "Invalid response from server");
            sendData = null;
          }
          if (sendData) {
            setManagementEmailSent(sendData.success === true);
            setManagementEmailError(sendData.success ? null : (sendData.error || "Send failed"));
          }
        } catch (e) {
          setManagementEmailSent(false);
          setManagementEmailError(e.message || "Network error — check Vercel logs for /api/send-email");
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

      {gradeError && <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#dc2626", fontSize: 13, marginBottom: 14 }}>{gradeError}</div>}

      <button onClick={handleGrade} disabled={loading} style={{ width: "100%", padding: "14px 24px", background: loading ? "#B88AFF" : "linear-gradient(135deg, #8A5CF6 0%, #B88AFF 100%)", color: "#fff", border: "none", borderRadius: 12, fontSize: 14, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 10, boxShadow: loading ? "none" : "0 4px 16px rgba(138,92,246,0.35)", transition: "all 0.15s" }}>
        {loading
          ? <><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2.5" style={{ animation: "spin 0.8s linear infinite", flexShrink: 0 }}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>Grading session + generating emails…</>
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
              Grade 515+, Intensive, or CARS sessions. Paste transcript and student notes to grade and send the management email to directors.
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
                {score !== null && <ScoreRing score={score} />}
                <div style={{ flex: 1, minWidth: 180 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573", marginBottom: 6 }}>Grading complete</p>
                  <div style={{ marginBottom: 7 }}>{rating && <RatingBadge rating={rating} />}</div>
                  <p style={{ fontSize: 12, color: "#5E6573" }}>{[form.tutorName, form.studentName, `Session ${form.sessionNumber}`, form.sessionDate].filter(Boolean).join(" · ")}</p>
                </div>
                <button onClick={() => navigator.clipboard.writeText(report)} style={{ padding: "8px 16px", border: "1.5px solid #8A5CF6", borderRadius: 10, background: "#fff", color: "#8A5CF6", fontSize: 12, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>Copy report</button>
              </div>

              {/* Score bands */}
              <div style={{ background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 10, padding: "11px 16px", marginBottom: 10, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#5E6573" }}>Score bands</span>
                {[["90–100","#16a34a","#f0fdf4","#bbf7d0","Exceeds"],["75–89","#2563eb","#eff6ff","#bfdbfe","Meets"],["60–74","#d97706","#fffbeb","#fde68a","Coach"],["<60","#dc2626","#fef2f2","#fecaca","Remediate"]].map(([range,c,bg,b,l])=>(
                  <span key={range} style={{padding:"3px 10px",borderRadius:8,background:bg,border:`1px solid ${b}`,fontSize:11,color:c,fontWeight:600}}><strong>{range}</strong> — {l}</span>
                ))}
              </div>

              {/* Full grading report — first */}
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#5E6573", marginBottom: 8 }}>Full grading report</p>
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12, padding: "26px 26px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", marginBottom: 16 }}>
                <ReportRenderer text={report} />
              </div>

              {/* Email drafts — tutor first, then management (draft tutor email below full report) */}
              {emails && (
                <div style={{ marginBottom: 10 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#5E6573", marginBottom: 8 }}>Email drafts</p>
                  <EmailPanel title="Draft Tutor Email" subtitle={`To: ${form.tutorEmail || form.tutorName || "tutor"} · Detailed grading report`} tagColor="#8A5CF6" subject={emails.tutorEmail?.subject} body={emails.tutorEmail?.body} formatBody />
                  <div>
                    <EmailPanel title="Management Summary" subtitle="To: Anastasia, Molly, Carl, Adam · Triage + full tutor draft" tagColor="#f59e0b" subject={emails.managementEmail?.subject} body={emails.managementEmail?.body} />
                    {managementEmailSent === true && (
                      <p style={{ fontSize: 12, color: "#16a34a", fontWeight: 600, marginTop: 6 }}>✓ Management email sent to directors</p>
                    )}
                    {managementEmailSent === false && (
                      <div style={{ marginTop: 8, padding: "12px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8 }}>
                        <p style={{ fontSize: 13, color: "#dc2626", fontWeight: 600, marginBottom: 4 }}>Email not sent</p>
                        <p style={{ fontSize: 12, color: "#b91c1c", marginBottom: 6 }}>{managementEmailError || "Unknown error"}</p>
                        <p style={{ fontSize: 11, color: "#7f1d1d" }}>Check Vercel → Project → Logs (filter by /api/send-email) for details. Confirm SMTP_SERVER (hostname), FROM_EMAIL, SMTP_PASSWORD, and DIRECTOR_EMAIL or DIRECTOR_EMAILS are set in Vercel Environment Variables, then redeploy.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
