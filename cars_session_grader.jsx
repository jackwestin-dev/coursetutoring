import { useState, useRef } from "react";

// ─── Known JW tutors (from Calendly org roster) ───────────────────────────────
const JW_TUTORS = [
  { name: "Ian Abrams",         email: "ianabrams@jackwestin.com" },
  { name: "Aditya Gurbani",     email: "aditya@jackwestin.com" },
  { name: "Akshat Patwardhan",  email: "akshat@jackwestin.com" },
  { name: "Alexander Phillip",  email: "alexander@jackwestin.com" },
  { name: "Anita Paschall",     email: "anita@jackwestin.com" },
  { name: "Athavan Murugaanathan", email: "athavan@jackwestin.com" },
  { name: "Audrey Leonard",     email: "audrey@jackwestin.com" },
  { name: "Bayla Khrian",       email: "bayla@jackwestin.com" },
  { name: "Cole Crossett",      email: "cole@jackwestin.com" },
  { name: "Courtney Brandt",    email: "courtney@jackwestin.com" },
  { name: "Darya Sulkouskaya",  email: "darya@jackwestin.com" },
  { name: "Garrett Oleen",      email: "garrett@jackwestin.com" },
  { name: "Ian Phoenix",        email: "ian@jackwestin.com" },
  { name: "Isabella Impalli",   email: "isabella@jackwestin.com" },
  { name: "Jesse Grossman",     email: "jesse@jackwestin.com" },
  { name: "Joseph Toth",        email: "joseph@jackwestin.com" },
  { name: "Joshua Dinii",       email: "joshua@jackwestin.com" },
  { name: "Kris Gamble",        email: "kris@jackwestin.com" },
  { name: "Livana Pichardo",    email: "livana@jackwestin.com" },
  { name: "Mark White",         email: "mark@jackwestin.com" },
  { name: "Marwan Abdrabou",    email: "marwan@jackwestin.com" },
  { name: "Matthew Cohen",      email: "matthewc@jackwestin.com" },
  { name: "Nicholas McDonald",  email: "nickm@jackwestin.com" },
  { name: "Olivia Helou",       email: "olivia@jackwestin.com" },
  { name: "Paul Walker",        email: "paulw@jackwestin.com" },
  { name: "Renee Light",        email: "reneel@jackwestin.com" },
  { name: "Steven Faragalla",   email: "steven@jackwestin.com" },
  { name: "Tejas Prasanna",     email: "tejas@jackwestin.com" },
  { name: "Thomas Fuller",      email: "thomas@jackwestin.com" },
  { name: "Tyler Falk",         email: "tylerfalk@jackwestin.com" },
  { name: "William Walsh",      email: "william@jackwestin.com" },
  { name: "Zander Roemer",      email: "zander@jackwestin.com" },
];

const TUTOR_FIRST_NAMES = new Set(JW_TUTORS.map(t => t.name.split(" ")[0].toLowerCase()));
const TUTOR_FULL_NAMES  = new Set(JW_TUTORS.map(t => t.name.toLowerCase()));

// Match a meeting participant name against the JW tutor roster
function matchTutor(participantName) {
  if (!participantName) return null;
  const lower = participantName.toLowerCase().trim();
  // Full name match first
  const full = JW_TUTORS.find(t => t.name.toLowerCase() === lower);
  if (full) return full;
  // Partial: first name match
  const first = JW_TUTORS.find(t => t.name.toLowerCase().startsWith(lower) || lower.startsWith(t.name.split(" ")[0].toLowerCase()));
  return first || null;
}

// ─── Fathom API (via Vercel proxy) ───────────────────────────────────────────
// Key lives in FATHOM_API_KEY env var on Vercel — never touches the browser
async function fathomGet(path) {
  const [pathname, qs] = path.split("?");
  const proxyUrl = `/api/fathom?path=${encodeURIComponent(pathname)}${qs ? `&${qs}` : ""}`;
  const r = await fetch(proxyUrl);
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`Fathom ${r.status}: ${body.slice(0, 120)}`);
  }
  return r.json();
}

function formatTranscript(rawData) {
  // Handle array of segments directly
  const segments = Array.isArray(rawData)
    ? rawData
    : (rawData?.transcript || rawData?.segments || rawData?.utterances || []);

  if (!segments.length) {
    return typeof rawData === "string" ? rawData : (rawData?.text || rawData?.content || "");
  }

  return segments.map(s => {
    const speaker = typeof s.speaker === "object"
      ? (s.speaker?.display_name || s.speaker?.name || "Unknown")
      : (s.speaker || "Unknown");
    const ts = s.timestamp ? `[${s.timestamp}] ` : "";
    return `${ts}${speaker}: ${(s.text || s.content || "").trim()}`;
  }).filter(Boolean).join("\n\n");
}

// ─── Grading system prompt ────────────────────────────────────────────────────
const GRADING_PROMPT = `You are the JW CARS Session Grader, an internal QA agent for Jack Westin MCAT CARS Strategy Course tutoring.

CORE GRADING RULES
1. Grade the NOTES primarily. Transcript reveals what SHOULD be documented and assesses live coaching quality.
2. Evidence must be explicit. No credit for implied content. Partial credit when partial documentation exists.
3. Score conservatively when uncertain.
4. SOP VERIFICATION INPUTS (THIRD SOURCE OF TRUTH): The grader may provide manual SOP verification inputs for: study schedule, AAMC question packs, and full-length exams. These are a fail-safe alongside transcript and student notes. Scoring: YES = full credit for that sub-item, PARTIAL = 50% credit, NO = 0 points UNLESS transcript or student notes confirm otherwise. Any source confirming the item can override a "No" from another source.

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

// ─── UI helpers ───────────────────────────────────────────────────────────────
function ReportRenderer({ text }) {
  const lines = text.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("## ")) {
      out.push(<h2 key={i} style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6c47ff", borderBottom: "1px solid #ece9ff", paddingBottom: 8, marginTop: 32, marginBottom: 14 }}>{line.replace("## ", "")}</h2>);
    } else if (line.startsWith("### ")) {
      out.push(<h3 key={i} style={{ fontSize: 14, fontWeight: 600, color: "#1a1a2e", marginTop: 20, marginBottom: 6 }}>{line.replace("### ", "")}</h3>);
    } else if (line.startsWith("| ")) {
      const tLines = [];
      while (i < lines.length && lines[i].startsWith("|")) { tLines.push(lines[i]); i++; }
      const rows = tLines.filter(l => !/^\|[-:\s|]+\|$/.test(l));
      out.push(
        <div key={`t${i}`} style={{ overflowX: "auto", margin: "12px 0", borderRadius: 8, border: "1px solid #ebebf0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>{rows.map((row, ri) => {
              const cells = row.split("|").slice(1, -1);
              const isH = ri === 0;
              return <tr key={ri} style={{ borderBottom: ri < rows.length - 1 ? "1px solid #ebebf0" : "none" }}>
                {cells.map((cell, ci) => {
                  const clean = cell.trim().replace(/\*\*/g, "");
                  return isH
                    ? <th key={ci} style={{ textAlign: "left", padding: "8px 14px", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#888", background: "#fafafa", borderBottom: "2px solid #ece9ff" }}>{clean}</th>
                    : <td key={ci} style={{ padding: "8px 14px", color: "#333", background: ri % 2 === 0 ? "#fff" : "#fdfcff", fontSize: 13 }}>{clean}</td>;
                })}
              </tr>;
            })}</tbody>
          </table>
        </div>
      );
      continue;
    } else if (/^\d+\.\s/.test(line)) {
      out.push(<div key={i} style={{ display: "flex", gap: 10, margin: "4px 0", alignItems: "flex-start" }}><span style={{ color: "#6c47ff", fontWeight: 700, fontSize: 13, minWidth: 20 }}>{line.match(/^(\d+)\./)[1]}.</span><span style={{ color: "#444", fontSize: 13, lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: line.replace(/^\d+\.\s/, "").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} /></div>);
    } else if (line.startsWith("- ")) {
      out.push(<div key={i} style={{ display: "flex", gap: 9, margin: "3px 0", alignItems: "flex-start" }}><span style={{ color: "#6c47ff", fontSize: 8, marginTop: 6, flexShrink: 0 }}>●</span><span style={{ color: "#555", fontSize: 13, lineHeight: 1.65 }} dangerouslySetInnerHTML={{ __html: line.replace(/^-\s/, "").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} /></div>);
    } else if (line.startsWith("**") && line.endsWith("**")) {
      out.push(<p key={i} style={{ fontWeight: 700, color: "#1a1a2e", margin: "10px 0 4px", fontSize: 13 }}>{line.replace(/\*\*/g, "")}</p>);
    } else if (line === "---") {
      out.push(<hr key={i} style={{ border: "none", borderTop: "1px solid #ebebf0", margin: "24px 0" }} />);
    } else if (!line.trim()) {
      out.push(<div key={i} style={{ height: 4 }} />);
    } else {
      out.push(<p key={i} style={{ color: "#555", fontSize: 13, lineHeight: 1.7, margin: "3px 0" }} dangerouslySetInnerHTML={{ __html: line.replace(/\*\*([^*]+)\*\*/g, "<strong style='color:#1a1a2e'>$1</strong>") }} />);
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
  const color = pct >= 90 ? "#16a34a" : pct >= 75 ? "#6c47ff" : pct >= 60 ? "#d97706" : "#dc2626";
  return (
    <div style={{ position: "relative", width: 88, height: 88, flexShrink: 0 }}>
      <svg width={88} height={88} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={44} cy={44} r={r} fill="none" stroke="#ebebf0" strokeWidth={7} />
        <circle cx={44} cy={44} r={r} fill="none" stroke={color} strokeWidth={7} strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 19, fontWeight: 800, color: "#1a1a2e", lineHeight: 1 }}>{score}</span>
        <span style={{ fontSize: 10, color: "#bbb", fontWeight: 500 }}>/100</span>
      </div>
    </div>
  );
}

function EmailPanel({ title, subtitle, tagColor, subject, body }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ border: "1px solid #e8e8f0", borderRadius: 10, overflow: "hidden", marginBottom: 10 }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "13px 16px", background: "#fafafa", cursor: "pointer", userSelect: "none" }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: tagColor, flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#1a1a2e" }}>{title}</div>
          <div style={{ fontSize: 11, color: "#aaa", marginTop: 1 }}>{subtitle}</div>
        </div>
        <span style={{ fontSize: 16, color: "#bbb", transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>›</span>
      </div>
      {open && (
        <div style={{ padding: "14px 16px", background: "#fff", borderTop: "1px solid #e8e8f0" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#aaa", marginBottom: 4 }}>Subject</div>
          <div style={{ fontSize: 13, color: "#1a1a2e", fontWeight: 500, marginBottom: 12 }}>{subject}</div>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#aaa", marginBottom: 4 }}>Body</div>
          <pre style={{ fontSize: 12, color: "#444", lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word", background: "#f7f7fb", border: "1px solid #ebebf0", borderRadius: 8, padding: "12px 14px", fontFamily: "inherit", maxHeight: 300, overflowY: "auto", marginBottom: 10 }}>{body}</pre>
          <button onClick={() => { navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
            style={{ padding: "7px 14px", background: copied ? "#6c47ff" : "#fff", border: "1.5px solid #6c47ff", borderRadius: 7, color: copied ? "#fff" : "#6c47ff", fontSize: 12, fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>
            {copied ? "Copied!" : "Copy email"}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Recording card ───────────────────────────────────────────────────────────
function RecordingCard({ rec, selected, onSelect }) {
  const tutor = rec.matchedTutor;
  const date = rec.date ? new Date(rec.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";
  const time = rec.date ? new Date(rec.date).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "";
  const hasTranscript = !!rec.transcript;

  return (
    <div onClick={() => onSelect(rec)} style={{
      padding: "13px 15px", borderRadius: 10, cursor: "pointer", userSelect: "none",
      border: selected ? "2px solid #6c47ff" : "1.5px solid #e2e2eb",
      background: selected ? "#faf8ff" : "#fff", transition: "all 0.15s",
      display: "flex", alignItems: "flex-start", gap: 12,
    }}>
      <div style={{ width: 10, height: 10, borderRadius: "50%", background: hasTranscript ? "#16a34a" : "#f59e0b", marginTop: 4, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#1a1a2e", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {rec.title || `Session — ${tutor?.name || "Unknown tutor"}`}
          </div>
          <div style={{ fontSize: 11, color: "#aaa", whiteSpace: "nowrap", flexShrink: 0 }}>{date}</div>
        </div>
        <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
          {tutor ? `${tutor.name}` : "Unmatched"}{time ? ` · ${time}` : ""}
          {rec.participants?.length > 0 && ` · ${rec.participants.slice(0,3).join(", ")}`}
        </div>
        <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
          {hasTranscript
            ? <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: "#f0fdf4", color: "#16a34a", border: "1px solid #bbf7d0" }}>Transcript ready</span>
            : <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: "#fffbeb", color: "#d97706", border: "1px solid #fde68a" }}>Transcript loading…</span>}
          {tutor && <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe" }}>JW Tutor matched</span>}
        </div>
      </div>
    </div>
  );
}

const inputBase = { width: "100%", padding: "10px 14px", border: "1.5px solid #e2e2eb", borderRadius: 8, fontSize: 13, color: "#1a1a2e", background: "#fff", outline: "none", fontFamily: "inherit", transition: "border-color 0.15s, box-shadow 0.15s" };

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function CARSGrader() {
  const [tab, setTab] = useState("fathom");

  // Fathom sync state
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);
  const [syncStatus, setSyncStatus] = useState("");
  const [recordings, setRecordings] = useState([]); // all JW-tutor-matched recordings
  const [selectedRec, setSelectedRec] = useState(null);

  // Form
  const [form, setForm] = useState({
    studentName: "", tutorName: "", tutorEmail: "",
    sessionDate: new Date().toISOString().split("T")[0],
    sessionNumber: "1", transcript: "", studentDoc: "", studySchedule: "",
    sopStudyScheduleUrl: "", sopStudySchedule: "no", sopQuestionPacks: "no", sopFullLengthExams: "no",
  });
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  // Grading
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [emails, setEmails] = useState(null);
  const [score, setScore] = useState(null);
  const [rating, setRating] = useState(null);
  const [gradeError, setGradeError] = useState(null);
  const [managementEmailSent, setManagementEmailSent] = useState(false);
  const [managementEmailError, setManagementEmailError] = useState(null);
  const reportRef = useRef(null);

  // ── Fathom sync ─────────────────────────────────────────────────────────────
  const handleFathomSync = async () => {
    setSyncError(null); setRecordings([]); setSelectedRec(null);
    setSyncing(true); setSyncStatus("Fetching meetings from Fathom…");

    try {
      // Step 1: List meetings
      const data = await fathomGet("/meetings?limit=100");
      const meetings = data.meetings || data.data || (Array.isArray(data) ? data : []);
      setSyncStatus(`Found ${meetings.length} meetings. Matching JW tutors…`);

      // Step 2: Filter to meetings where a JW tutor is a participant
      const matched = [];
      for (const m of meetings) {
        const participants = m.participants || m.attendees || [];
        const participantNames = participants.map(p =>
          typeof p === "string" ? p : (p.display_name || p.name || p.email || "")
        );

        // Check every participant name against JW roster
        let tutorMatch = null;
        for (const pName of participantNames) {
          tutorMatch = matchTutor(pName);
          if (tutorMatch) break;
        }
        // Also check the meeting title / host
        if (!tutorMatch && m.title) tutorMatch = matchTutor(m.title);
        if (!tutorMatch && m.host) tutorMatch = matchTutor(typeof m.host === "object" ? (m.host.name || m.host.display_name) : m.host);

        if (!tutorMatch) continue;

        const recId = m.recording?.id || m.id;
        const recDate = m.started_at || m.created_at || m.date || m.scheduled_at || "";
        const otherParticipants = participantNames.filter(n => !matchTutor(n) && n);

        matched.push({
          id: recId,
          title: m.title || m.name || "",
          date: recDate,
          matchedTutor: tutorMatch,
          participants: otherParticipants,
          transcript: null, // loaded lazily below
          rawMeeting: m,
        });
      }

      setSyncStatus(`Matched ${matched.length} JW tutor sessions. Fetching transcripts…`);

      // Step 3: Fetch transcripts for all matched recordings (in parallel, batched)
      const withTranscripts = [...matched];
      const BATCH = 5;
      for (let i = 0; i < matched.length; i += BATCH) {
        const batch = matched.slice(i, i + BATCH);
        await Promise.all(batch.map(async (rec, bi) => {
          try {
            const tData = await fathomGet(`/recordings/${rec.id}/transcript`);
            withTranscripts[i + bi].transcript = formatTranscript(tData);
          } catch (e) {
            withTranscripts[i + bi].transcript = null;
            withTranscripts[i + bi].transcriptError = e.message;
          }
        }));
        const done = Math.min(i + BATCH, matched.length);
        setSyncStatus(`Fetched ${done}/${matched.length} transcripts…`);
        setRecordings([...withTranscripts]);
      }

      // Sort by date descending
      withTranscripts.sort((a, b) => new Date(b.date) - new Date(a.date));
      setRecordings(withTranscripts);

      const withT = withTranscripts.filter(r => r.transcript).length;
      setSyncStatus(`Done — ${matched.length} sessions, ${withT} with transcripts`);
    } catch (e) {
      setSyncError(e.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleSelectRecording = (rec) => {
    setSelectedRec(rec);
    setReport(null); setEmails(null); setScore(null); setRating(null);
    const student = rec.participants?.[0] || "";
    const sessionDateStr = rec.date ? rec.date.split("T")[0] : new Date().toISOString().split("T")[0];
    setForm(f => ({
      ...f,
      tutorName: rec.matchedTutor?.name || f.tutorName,
      tutorEmail: rec.matchedTutor?.email || f.tutorEmail,
      studentName: student,
      sessionDate: sessionDateStr,
      transcript: rec.transcript || f.transcript,
    }));
  };

  // ── Claude calls ─────────────────────────────────────────────────────────────
  const callClaude = async (system, msg) => {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: "claude-sonnet-4-20250514", max_tokens: 4000, system, messages: [{ role: "user", content: msg }] }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    return data.content.filter(b => b.type === "text").map(b => b.text).join("\n");
  };

  const handleGrade = async () => {
    if (!form.transcript.trim() || !form.studentDoc.trim()) {
      setGradeError("Please provide both the session transcript and student notes document."); return;
    }
    setGradeError(null); setReport(null); setEmails(null); setScore(null); setRating(null); setManagementEmailSent(false); setManagementEmailError(null); setLoading(true);
    try {
      const sopVerification = `\n\nSOP VERIFICATION (manual input — third source of truth):\n- Study schedule provided in Google Sheet: ${form.sopStudySchedule.toUpperCase()}${form.sopStudyScheduleUrl ? ` (URL: ${form.sopStudyScheduleUrl})` : ""}\n- AAMC question packs assigned: ${form.sopQuestionPacks.toUpperCase()}\n- Ten full-length exams assigned: ${form.sopFullLengthExams.toUpperCase()}\n\nSOP VERIFICATION RULES:\n- YES = full credit for that SOP sub-item\n- PARTIAL = 50% credit for that SOP sub-item\n- NO = 0 points for that SOP sub-item UNLESS the transcript or student notes confirm otherwise (other sources can override a "No")\n- These manual inputs are a fail-safe — treat them as a third source of truth alongside transcript and student notes`;
      const gradeText = await callClaude(GRADING_PROMPT,
        `STUDENT: ${form.studentName||"Not provided"}\nTUTOR: ${form.tutorName||"Not provided"}\nSESSION: ${form.sessionNumber}\nDATE: ${form.sessionDate}\n\nTRANSCRIPT:\n${form.transcript}\n\nSTUDENT NOTES:\n${form.studentDoc}\n\nSTUDY SCHEDULE (reference only):\n${form.studySchedule||"Not provided"}${sopVerification}`
      );
      setReport(gradeText);

      const sm = gradeText.match(/Scaled Score[^:*\n]*:?\*?\s*(\d+)\/100/i);
      const ps = sm ? parseInt(sm[1]) : null;
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
      // Send management email to directors via /api/send-email
      if (parsed?.managementEmail) {
        try {
          const sendRes = await fetch("/api/send-email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              subject: parsed.managementEmail.subject,
              body: parsed.managementEmail.body,
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
      setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
    } catch (e) { setGradeError(e.message); }
    finally { setLoading(false); }
  };

  const withTranscriptCount = recordings.filter(r => r.transcript).length;

  const GradeForm = ({ showTranscriptBadge }) => (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        {[{ k: "studentName", l: "Student Name", t: "text", ph: "e.g. Jordan Kim" },
          { k: "tutorName",   l: "Tutor Name",   t: "text", ph: "e.g. Sarah Chen" },
          { k: "tutorEmail",  l: "Tutor Email",  t: "email", ph: "tutor@jackwestin.com" },
          { k: "sessionDate", l: "Session Date", t: "date", ph: "" },
        ].map(({ k, l, t, ph }) => (
          <div key={k} style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 6 }}>{l}</label>
            <input type={t} placeholder={ph} value={form[k]} onChange={set(k)} style={inputBase} />
          </div>
        ))}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 6 }}>Session Number</label>
        <select value={form.sessionNumber} onChange={set("sessionNumber")} style={{ ...inputBase, cursor: "pointer", appearance: "none", backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23aaa' stroke-width='2.5'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 13px center", paddingRight: 36 }}>
          <option value="1">Session 1 — Onboarding &amp; Plan Build</option>
          <option value="2">Session 2 — Adherence &amp; Adjustment</option>
          <option value="3">Session 3 — Timed Pressure &amp; Diagnostics</option>
        </select>
      </div>
      <div style={{ height: 1, background: "#e8e8f0", margin: "4px 0 16px" }} />

      {/* Transcript */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: "#444" }}>Session Transcript <span style={{ color: "#dc2626" }}>*</span></label>
          {showTranscriptBadge && selectedRec?.transcript &&
            <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 8, background: "#f0fdf4", color: "#16a34a", border: "1px solid #bbf7d0" }}>✓ Auto-loaded from Fathom</span>}
          {showTranscriptBadge && !selectedRec?.transcript &&
            <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 8, background: "#fffbeb", color: "#d97706", border: "1px solid #fde68a" }}>No Fathom transcript — paste manually</span>}
        </div>
        <textarea rows={7} placeholder="Paste the full session transcript here…" value={form.transcript} onChange={set("transcript")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 6 }}>
          Student Notes Document <span style={{ color: "#dc2626" }}>*</span>
          <span style={{ fontWeight: 400, color: "#bbb", fontSize: 11, marginLeft: 8 }}>Primary artifact being graded</span>
        </label>
        <textarea rows={7} placeholder="Paste the Course Tutoring Notes Template contents…" value={form.studentDoc} onChange={set("studentDoc")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 6 }}>
          Study Schedule
          <span style={{ fontWeight: 400, color: "#bbb", fontSize: 11, marginLeft: 8 }}>Reference only — not graded</span>
        </label>
        <textarea rows={3} placeholder="Optional…" value={form.studySchedule} onChange={set("studySchedule")} style={{ ...inputBase, resize: "vertical", lineHeight: 1.6 }} />
      </div>

      {/* SOP Verification */}
      <div style={{ height: 1, background: "#E5E7EB", margin: "4px 0 16px" }} />
      <div style={{ marginBottom: 18 }}>
        <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6c47ff", marginBottom: 14 }}>SOP Verification</p>
        <p style={{ fontSize: 12, color: "#888", marginBottom: 16, lineHeight: 1.6 }}>Manual confirmation of key SOP items. These inputs act as a third source of truth alongside the transcript and student notes.</p>

        {/* Study Schedule */}
        <div style={{ marginBottom: 16, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 8 }}>Study schedule provided in a Google Sheet</label>
          <input type="url" placeholder="https://docs.google.com/spreadsheets/d/..." value={form.sopStudyScheduleUrl} onChange={set("sopStudyScheduleUrl")} style={{ ...inputBase, marginBottom: 10 }} />
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopStudySchedule: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopStudySchedule === val ? "#6c47ff" : "#E5E7EB"}`, background: form.sopStudySchedule === val ? "#ede9fe" : "#fff", color: form.sopStudySchedule === val ? "#6c47ff" : "#888", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* AAMC Question Packs */}
        <div style={{ marginBottom: 16, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 8 }}>Have the AAMC question packs been assigned?</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopQuestionPacks: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopQuestionPacks === val ? "#6c47ff" : "#E5E7EB"}`, background: form.sopQuestionPacks === val ? "#ede9fe" : "#fff", color: form.sopQuestionPacks === val ? "#6c47ff" : "#888", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Full-Length Exams */}
        <div style={{ marginBottom: 4, padding: "14px 16px", background: "#F9FAFB", borderRadius: 10, border: "1px solid #E5E7EB" }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#444", marginBottom: 8 }}>Have ten full-length exams been assigned?</label>
          <div style={{ display: "flex", gap: 8 }}>
            {[["yes", "Yes"], ["partial", "Partial"], ["no", "No"]].map(([val, label]) => (
              <label key={val} onClick={() => setForm(f => ({ ...f, sopFullLengthExams: val }))} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 12px", borderRadius: 8, border: `1.5px solid ${form.sopFullLengthExams === val ? "#6c47ff" : "#E5E7EB"}`, background: form.sopFullLengthExams === val ? "#ede9fe" : "#fff", color: form.sopFullLengthExams === val ? "#6c47ff" : "#888", fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.15s", userSelect: "none" }}>
                {label}
              </label>
            ))}
          </div>
        </div>
      </div>

      {gradeError && <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#dc2626", fontSize: 13, marginBottom: 14 }}>{gradeError}</div>}

      <button onClick={handleGrade} disabled={loading} style={{ width: "100%", padding: "13px", background: loading ? "#a78bfa" : "#6c47ff", color: "#fff", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 10, boxShadow: loading ? "none" : "0 4px 16px rgba(108,71,255,0.3)", transition: "all 0.15s" }}>
        {loading
          ? <><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2.5" style={{ animation: "spin 0.8s linear infinite", flexShrink: 0 }}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>Grading session + generating email drafts…</>
          : "Grade this session →"}
      </button>
    </>
  );

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #f4f4f8 !important; }
        input:focus, textarea:focus, select:focus { border-color: #6c47ff !important; box-shadow: 0 0 0 3px rgba(108,71,255,0.12) !important; outline: none; }
        textarea { font-family: 'Inter', sans-serif; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .rlist { max-height: 420px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
        .rlist::-webkit-scrollbar { width: 4px; }
        .rlist::-webkit-scrollbar-thumb { background: #e2e2eb; border-radius: 2px; }
      `}</style>

      <div style={{ minHeight: "100vh", background: "#f4f4f8", fontFamily: "'Inter', sans-serif", paddingBottom: 80 }}>

        {/* Nav */}
        <nav style={{ background: "#fff", borderBottom: "1px solid #e8e8f0", padding: "0 24px", height: 52, display: "flex", alignItems: "center", position: "sticky", top: 0, zIndex: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 26, height: 26, borderRadius: 6, background: "linear-gradient(135deg, #6c47ff 0%, #a78bfa 100%)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ color: "#fff", fontSize: 10, fontWeight: 800 }}>JW</span>
            </div>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#1a1a2e" }}>CARS Session Grader</span>
            <span style={{ width: 1, height: 14, background: "#e2e2eb", margin: "0 4px" }} />
            <span style={{ fontSize: 12, color: "#aaa" }}>Internal QA Tool</span>
          </div>
        </nav>

        <div style={{ maxWidth: 780, margin: "0 auto", padding: "40px 20px 0" }}>

          {/* Hero */}
          <div style={{ marginBottom: 28 }}>
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#6c47ff", textTransform: "uppercase", marginBottom: 10 }}>The CARS Strategy Course</p>
            <h1 style={{ fontSize: "clamp(24px, 4vw, 34px)", fontWeight: 800, color: "#1a1a2e", lineHeight: 1.15, letterSpacing: "-0.025em", marginBottom: 10 }}>Session grading, powered by AI.</h1>
            <p style={{ fontSize: 14, color: "#666", lineHeight: 1.65, maxWidth: 560 }}>
              Sync with Fathom to auto-load transcripts for any JW tutor session, then grade in one click.
            </p>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
            {[["fathom", "Sync from Fathom"], ["manual", "Manual entry"]].map(([t, l]) => (
              <button key={t} onClick={() => setTab(t)} style={{ padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", border: tab === t ? "none" : "1.5px solid #e2e2eb", background: tab === t ? "#6c47ff" : "#fff", color: tab === t ? "#fff" : "#666", boxShadow: tab === t ? "0 2px 8px rgba(108,71,255,0.25)" : "none", transition: "all 0.15s" }}>
                {l}
              </button>
            ))}
          </div>

          {/* ── FATHOM TAB ── */}
          {tab === "fathom" && (
            <div style={{ animation: "fadeUp 0.2s ease" }}>

              {/* Sync card */}
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e8e8f0", padding: "22px 24px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", marginBottom: 14 }}>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#bbb", marginBottom: 14 }}>Fathom sync</p>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                  <p style={{ fontSize: 13, color: "#666", lineHeight: 1.5 }}>
                    Pulls all recent meetings from Fathom and matches sessions where a JW tutor is a participant.
                    <br/><span style={{ fontSize: 11, color: "#aaa" }}>API key configured via <code style={{ background: "#f4f4f8", padding: "1px 5px", borderRadius: 4, fontSize: 11 }}>FATHOM_API_KEY</code> environment variable.</span>
                  </p>
                  <button onClick={handleFathomSync} disabled={syncing} style={{ padding: "10px 20px", background: syncing ? "#a78bfa" : "#6c47ff", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: syncing ? "not-allowed" : "pointer", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8, boxShadow: syncing ? "none" : "0 2px 10px rgba(108,71,255,0.28)", transition: "all 0.15s", flexShrink: 0 }}>
                    {syncing
                      ? <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2.5" style={{ animation: "spin 0.8s linear infinite" }}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>Syncing…</>
                      : "↻ Sync Fathom"}
                  </button>
                </div>
                {syncError && <div style={{ marginTop: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#dc2626", fontSize: 13 }}>{syncError}</div>}
                {syncStatus && <p style={{ fontSize: 12, color: "#888", marginTop: 10 }}>{syncStatus}</p>}
                {recordings.length > 0 && (
                  <div style={{ marginTop: 12, display: "flex", gap: 16, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 5, color: "#16a34a" }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#16a34a", display: "inline-block" }} />Transcript ready ({withTranscriptCount})</span>
                    <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 5, color: "#d97706" }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />No transcript ({recordings.length - withTranscriptCount})</span>
                  </div>
                )}
              </div>

              {/* Recordings list */}
              {recordings.length > 0 && (
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e8e8f0", padding: "18px 18px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", marginBottom: 14 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#bbb", marginBottom: 12 }}>
                    {recordings.length} JW tutor sessions found — select one to grade
                  </p>
                  <div className="rlist">
                    {recordings.map((r, i) => (
                      <RecordingCard key={i} rec={r} selected={selectedRec === r} onSelect={handleSelectRecording} />
                    ))}
                  </div>
                </div>
              )}

              {/* Grade form — shown when a recording is selected */}
              {selectedRec && (
                <div style={{ background: "#fff", borderRadius: 12, border: "2px solid #6c47ff", padding: "22px 24px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", animation: "fadeUp 0.2s ease" }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6c47ff", marginBottom: 16 }}>Grade selected session</p>
                  <GradeForm showTranscriptBadge={true} />
                </div>
              )}
            </div>
          )}

          {/* ── MANUAL TAB ── */}
          {tab === "manual" && (
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e8e8f0", padding: "24px 24px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", animation: "fadeUp 0.2s ease" }}>
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#bbb", marginBottom: 16 }}>Session details</p>
              <GradeForm showTranscriptBadge={false} />
            </div>
          )}

          {/* ── RESULTS ── */}
          {report && (
            <div ref={reportRef} style={{ marginTop: 24, animation: "fadeUp 0.4s ease" }}>
              <div style={{ background: "#fff", border: "1px solid #e8e8f0", borderRadius: 12, padding: "18px 22px", marginBottom: 10, display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                {score !== null && <ScoreRing score={score} />}
                <div style={{ flex: 1, minWidth: 180 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#bbb", marginBottom: 6 }}>Grading complete</p>
                  <div style={{ marginBottom: 7 }}>{rating && <RatingBadge rating={rating} />}</div>
                  <p style={{ fontSize: 12, color: "#999" }}>{[form.tutorName, form.studentName, `Session ${form.sessionNumber}`, form.sessionDate].filter(Boolean).join(" · ")}</p>
                </div>
                <button onClick={() => navigator.clipboard.writeText(report)} style={{ padding: "7px 14px", border: "1.5px solid #6c47ff", borderRadius: 8, background: "#fff", color: "#6c47ff", fontSize: 12, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>Copy report</button>
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
              <div style={{ background: "#fafafa", border: "1px solid #e8e8f0", borderRadius: 10, padding: "11px 16px", marginBottom: 10, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#bbb" }}>Score bands</span>
                {[["90–100","#16a34a","#f0fdf4","#bbf7d0","Exceeds"],["75–89","#2563eb","#eff6ff","#bfdbfe","Meets"],["60–74","#d97706","#fffbeb","#fde68a","Coach"],["<60","#dc2626","#fef2f2","#fecaca","Remediate"]].map(([range,c,bg,b,l])=>(
                  <span key={range} style={{padding:"3px 10px",borderRadius:8,background:bg,border:`1px solid ${b}`,fontSize:11,color:c,fontWeight:600}}><strong>{range}</strong> — {l}</span>
                ))}
              </div>

              {emails && (
                <div style={{ marginBottom: 10 }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#aaa", marginBottom: 8 }}>Emails</p>
                  <EmailPanel title="Tutor Feedback Email" subtitle={`To: ${form.tutorEmail || form.tutorName || "tutor"} · Detailed grading report (draft only — not sent)`} tagColor="#6c47ff" subject={emails.tutorEmail?.subject} body={emails.tutorEmail?.body} />
                  <EmailPanel title="Management Report" subtitle={`To: Directors · ${managementEmailSent ? "Sent" : "Pending"}`} tagColor={managementEmailSent ? "#16a34a" : "#f59e0b"} subject={emails.managementEmail?.subject} body={emails.managementEmail?.body} />
                </div>
              )}

              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#aaa", marginBottom: 8 }}>Full grading report</p>
              <div style={{ background: "#fff", border: "1px solid #e8e8f0", borderRadius: 12, padding: "26px 26px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <ReportRenderer text={report} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
