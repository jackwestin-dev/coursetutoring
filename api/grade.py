# -*- coding: utf-8 -*-
"""Vercel Serverless Function for JW Session Grader"""

import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler

# Email config from environment (SMTP_SERVER = hostname only, e.g. smtp.office365.com)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
FROM_EMAIL = os.getenv('FROM_EMAIL', '')
SMTP_USER = (os.getenv('SMTP_USER', '') or FROM_EMAIL).strip()
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
DIRECTOR_EMAIL = os.getenv('DIRECTOR_EMAIL', 'anastasia@jackwestin.com')


class SessionGrader:
    """Grader for Session 1 tutoring notes."""

    def __init__(self, transcript, student_name, tutor_name, session_date, student_notes='',
                 sop_study_schedule='no', sop_question_packs='no', sop_full_length_exams='no'):
        self.transcript = transcript
        self.student_name = student_name
        self.tutor_name = tutor_name
        self.session_date = session_date
        self.student_notes = student_notes or ''
        self.sop_study_schedule = (sop_study_schedule or 'no').lower()
        self.sop_question_packs = (sop_question_packs or 'no').lower()
        self.sop_full_length_exams = (sop_full_length_exams or 'no').lower()
        self.findings = None
        self.scores = {}
        self.justifications = {}
        self.missing_items = {}
    
    def extract_info(self):
        """Extract key information from transcript."""
        text = self.transcript.lower()
        
        # Test date
        test_date = 'Not found'
        date_patterns = [
            r'test(?:ing)?\s+(?:date|day|is)?\s*(?:is|on|:)?\s*(\w+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)',
            r'(?:mcat|exam)\s+(?:is\s+)?(?:on\s+)?(\w+\s+\d{1,2})',
            r'april\s+\d{1,2}',
            r'(\d{1,2}/\d{1,2}/\d{2,4})'
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                test_date = match.group(0).title() if match.lastindex is None else match.group(1).title()
                break
        
        # Baseline score
        baseline = 'Not found'
        score_patterns = [r'(\d{3})\s*(?:on|diagnostic|baseline)', r'scored?\s*(?:a|an)?\s*(\d{3})', r'(\d{3})\s*(?:fl|full.?length)']
        for pattern in score_patterns:
            match = re.search(pattern, text)
            if match:
                baseline = match.group(1)
                break
        
        # Target score
        target = 'Not found'
        target_match = re.search(r'(?:target|goal|need|want)\s*(?:a|an|is|of)?\s*(\d{3})', text)
        if target_match:
            target = target_match.group(1)
        
        info = {
            'test_date': test_date,
            'baseline_score': baseline,
            'target_score': target,
            'has_adhd': 'adhd' in text or 'add' in text or 'attention' in text,
            'has_classes': 'class' in text or 'school' in text or 'semester' in text,
            'has_work': 'work' in text or 'job' in text,
            'weak_chem': 'chem' in text and ('weak' in text or 'struggle' in text or 'hard' in text),
            'weak_bio': 'bio' in text and ('weak' in text or 'struggle' in text),
            'strong_cars': 'cars' in text and ('strong' in text or 'good' in text or 'comfortable' in text),
            'strong_psych': 'psych' in text and ('strong' in text or 'good' in text),
            'has_strategy': 'strategy' in text or 'approach' in text or 'technique' in text,
            'has_next_session': 'next session' in text or 'next week' in text or 'two weeks' in text or 'three weeks' in text,
            'topics_discussed': self._extract_topics(),
            'transcript_length': len(self.transcript)
        }
        return info
    
    def _extract_topics(self):
        """Extract science topics discussed."""
        topics = []
        topic_keywords = {
            'Physics/Unit Analysis': ['physics', 'unit analysis', 'd=v', 'velocity', 'kinematics'],
            'Acid-Base Chemistry': ['acid', 'base', 'ph', 'pka', 'henderson', 'proton'],
            'Equilibrium/Ksp': ['equilibrium', 'ksp', 'le chatelier', 'precipitate'],
            'Enzyme Kinetics': ['enzyme', 'kinetics', 'michaelis', 'kcat', 'vmax'],
            'Action Potentials': ['action potential', 'neuron', 'sodium', 'potassium channel'],
            'Amino Acids': ['amino acid', 'protein structure', 'peptide'],
            'Passage Strategy': ['passage', 'experimental', 'triage', 'approach']
        }
        text = self.transcript.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in text for kw in keywords):
                topics.append(topic)
        return topics
    
    def _is_march5_placeholder(self, date_str):
        """Check if a date string is the March 5th default/placeholder date.

        The student notes sheet has a default date of 'March 5' pre-filled in
        the Planned Date column. If exams still show this date, the tutor did
        NOT actually schedule them. Returns True if the date matches any
        variation of March 5th.
        """
        if not date_str:
            return False
        d = date_str.strip().lower()
        march5_patterns = [
            r'^march\s*5(?:th)?$',
            r'^mar\s*5(?:th)?$',
            r'^3/0?5(?:/\d{2,4})?$',
            r'^03/05(?:/\d{2,4})?$',
        ]
        return any(re.search(p, d) for p in march5_patterns)

    def _count_march5_exams(self, text):
        """Count how many exam dates in the text are the March 5th placeholder.

        Scans the combined transcript + notes for exam schedule entries and
        checks if dates are the default March 5th placeholder. Returns a tuple
        of (total_exam_dates_found, march5_count).
        """
        if not text:
            return 0, 0
        date_pattern = r'(?:march\s*5(?:th)?|mar\s*5(?:th)?|3/0?5(?:/\d{2,4})?|03/05(?:/\d{2,4})?)'
        march5_matches = re.findall(date_pattern, text.lower())
        march5_count = len(march5_matches)

        all_dates = re.findall(
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}|\d{1,2}/\d{1,2}',
            text.lower()
        )
        total_dates = len(all_dates)
        return total_dates, march5_count

    def _check_student_notes_aamc(self):
        """Check if student notes document confirms AAMC materials were assigned/scheduled.

        The student notes document is an equally valid source of truth for AAMC
        scheduling. If it confirms AAMC materials were assigned, that alone is
        sufficient for full credit (dual-source rule).
        """
        if not self.student_notes:
            return False
        notes_lower = self.student_notes.lower()
        if 'aamc' not in notes_lower:
            return False
        confirmation_patterns = [
            r'aamc.*(?:assign|scheduled|complete|yes|done|plan|sequenc|deadline)',
            r'(?:assign|scheduled|complete|yes|done|plan|sequenc|deadline).*aamc',
            r'(?:all|every)\s+aamc',
            r'aamc\s+(?:fl|full.?length|section\s*bank|q.?pack)',
        ]
        return any(re.search(p, notes_lower) for p in confirmation_patterns)

    def check_notes_present(self):
        """Check what SOP items are in the notes."""
        text = self.transcript.lower()

        # AAMC dual-source rule: check both transcript AND student notes document
        student_doc_confirms_aamc = self._check_student_notes_aamc()

        checks = {
            'fl_exam_schedule': {'status': 'No', 'evidence': '(Not documented)'},
            'aamc_question_packs': {'status': 'No', 'evidence': '(Not documented)'},
            'below_avg_topics': {'status': 'No', 'evidence': '(Not documented)'},
            'weekly_checklist': {'status': 'No', 'evidence': '(Not documented)'},
            'daily_tasks': {'status': 'No', 'evidence': '(Not documented)'},
            'strategy_notes': {'status': 'No', 'evidence': '(Not documented)'},
            'next_session': {'status': 'No', 'evidence': '(Not documented)'},
            'google_doc_shared': {'status': 'No', 'evidence': '(Not documented)'},
            'baseline_documented': {'status': 'No', 'evidence': '(Not documented)'}
        }

        # Full-Length Exam schedule detection (JW FL, AAMC exams, full length, practice exam)
        # Check for March 5th placeholder dates in exam schedule
        combined_for_dates = text + ' ' + (self.student_notes or '').lower()
        total_dates, march5_count = self._count_march5_exams(combined_for_dates)

        fl_keywords = ['full length', 'full-length', 'jw fl', 'jack westin fl', 'practice exam', 'aamc fl']
        has_fl_ref = ('fl' in text and any(w in text for w in ['schedule', 'week', 'saturday', 'date'])) or any(kw in text for kw in fl_keywords)
        if has_fl_ref:
            if march5_count > 0 and total_dates > 0 and march5_count >= total_dates * 0.7:
                # Most/all exam dates are the March 5th placeholder — not actually scheduled
                checks['fl_exam_schedule'] = {'status': 'No', 'evidence': 'Exam dates use default March 5th placeholder — not actually scheduled by tutor'}
            elif march5_count > 0 and total_dates > march5_count:
                checks['fl_exam_schedule'] = {'status': 'Partial', 'evidence': 'Some exams scheduled but {} of {} dates are the March 5th default placeholder'.format(march5_count, total_dates)}
            else:
                checks['fl_exam_schedule'] = {'status': 'Partial', 'evidence': 'FL exam scheduling discussed'}

        # AAMC Question Packs/Resources detection (separate from exams)
        # Dual-source rule: student notes document is equally valid evidence
        qpack_keywords = ['question pack', 'q-pack', 'qpack', 'section bank', 'flashcard', 'official prep', 'diagnostic tool']
        has_no_aamc = 'no aamc' in text or "doesn't have aamc" in text or 'does not have aamc' in text or "don't have aamc" in text
        if has_no_aamc:
            checks['aamc_question_packs'] = {'status': 'Yes', 'evidence': 'Student has no AAMC question packs — full credit'}
        elif student_doc_confirms_aamc:
            checks['aamc_question_packs'] = {'status': 'Yes', 'evidence': 'Student notes document confirms AAMC materials assigned/scheduled'}
        elif any(kw in text for kw in qpack_keywords):
            checks['aamc_question_packs'] = {'status': 'Partial', 'evidence': 'AAMC question packs/resources mentioned'}
        elif 'aamc' in text and not any(kw in text for kw in ['exam', 'full length', 'full-length']):
            checks['aamc_question_packs'] = {'status': 'Partial', 'evidence': 'AAMC materials referenced (likely question packs)'}
        if any(w in text for w in ['weak', 'below', 'struggle', 'hard']):
            checks['below_avg_topics'] = {'status': 'Partial', 'evidence': 'Weak areas discussed'}
        if 'daily' in text or 'week 1' in text:
            checks['daily_tasks'] = {'status': 'Partial', 'evidence': 'Some daily tasks mentioned'}
        if any(w in text for w in ['strategy', 'approach', 'technique']):
            checks['strategy_notes'] = {'status': 'Partial', 'evidence': 'Strategy concepts taught'}
        if 'next' in text and ('session' in text or 'week' in text):
            checks['next_session'] = {'status': 'Partial', 'evidence': 'Next session timing discussed'}
        
        return checks
    
    def grade(self):
        """Perform grading and return findings."""
        info = self.extract_info()
        notes_check = self.check_notes_present()
        
        # Preparation score
        prep_score = 5
        prep_just = []
        prep_missing = []
        if info['test_date'] != 'Not found':
            prep_score += 1
            prep_just.append("Test date was discussed")
        else:
            prep_missing.append("Test date not confirmed")
        if info['baseline_score'] != 'Not found':
            prep_score += 1
            prep_just.append("baseline score reviewed")
        else:
            prep_missing.append("Baseline score not documented")
        if info['weak_chem'] or info['weak_bio']:
            prep_score += 1
            prep_just.append("weak areas identified")
        else:
            prep_missing.append("Below-average topics not identified")
        
        self.scores['Preparation'] = min(prep_score, 10)
        self.justifications['Preparation'] = ' '.join(prep_just) + ". However, no documentation of preparation exists in the notes." if prep_just else "Limited evidence of preparation in documentation."
        self.missing_items['Preparation'] = prep_missing if prep_missing else ["Documentation of baseline review", "Prioritized topic list"]
        
        # Study Plan score — incorporates SOP verification inputs as third source of truth
        plan_score = 3
        plan_just = []
        plan_missing = []
        # Full-length exams: check notes/transcript OR SOP verification
        fl_confirmed = notes_check['fl_exam_schedule']['status'] != 'No'
        if not fl_confirmed and self.sop_full_length_exams == 'yes':
            fl_confirmed = True
            plan_just.append("Full-length exams confirmed via SOP verification (YES)")
        elif not fl_confirmed and self.sop_full_length_exams == 'partial':
            plan_score += 1  # 50% credit
            plan_just.append("Full-length exams partially confirmed via SOP verification (PARTIAL)")
        if fl_confirmed:
            plan_score += 2
            if "Full-length exams confirmed via SOP verification" not in ' '.join(plan_just):
                plan_just.append("Some FL exam scheduling discussed")
        else:
            plan_missing.append("Full-length exam schedule with dates (10 exams: JW FL 1-6 + AAMC exams)")
        # AAMC question packs: check notes/transcript OR SOP verification
        aamc_confirmed = notes_check['aamc_question_packs']['status'] != 'No'
        if not aamc_confirmed and self.sop_question_packs == 'yes':
            aamc_confirmed = True
            plan_just.append("AAMC question packs confirmed via SOP verification (YES)")
        elif not aamc_confirmed and self.sop_question_packs == 'partial':
            plan_score += 1  # partial credit
            plan_just.append("AAMC question packs partially confirmed via SOP verification (PARTIAL)")
        if aamc_confirmed:
            plan_score += 1
            if "AAMC question packs confirmed via SOP verification" not in ' '.join(plan_just):
                plan_just.append("AAMC question packs/resources referenced")
        else:
            plan_missing.append("AAMC question packs/resources scheduling (if student has them)")
        # Study schedule: check SOP verification
        if self.sop_study_schedule == 'yes':
            plan_score += 1
            plan_just.append("Study schedule confirmed via SOP verification (YES)")
        elif self.sop_study_schedule == 'partial':
            plan_just.append("Study schedule partially confirmed via SOP verification (PARTIAL)")
        if notes_check['weekly_checklist']['status'] != 'No':
            plan_score += 2
        else:
            plan_missing.append("Weekly checklist")
        if notes_check['daily_tasks']['status'] != 'No':
            plan_score += 1
        else:
            plan_missing.append("Daily tasks for Week 1")
        
        self.scores['Study Plan'] = min(plan_score, 10)
        self.justifications['Study Plan'] = ' '.join(plan_just) + " However, notes contain minimal structured study plan documentation." if plan_just else "The notes contain minimal to no structured study plan. No weekly checklist, no AAMC question pack scheduling, and limited daily task assignments are documented."
        self.missing_items['Study Plan'] = plan_missing if plan_missing else ["Structured exam schedule", "Weekly checklist", "Daily tasks"]
        
        # Personalization score
        pers_score = 5
        pers_just = []
        pers_missing = []
        if info['has_adhd']:
            pers_score += 1
            pers_just.append("ADHD accommodations acknowledged")
        if info['has_classes']:
            pers_score += 1
            pers_just.append("school schedule considered")
        if info['has_work']:
            pers_score += 1
        if not pers_just:
            pers_just.append("Limited personalization evident in documentation")
        pers_missing.append("Weekly study hour estimate")
        pers_missing.append("Documented workload calibration")
        
        self.scores['Personalization'] = min(pers_score, 10)
        self.justifications['Personalization'] = ' '.join(pers_just) + ". However, these factors were not translated into documented workload calibration."
        self.missing_items['Personalization'] = pers_missing
        
        # Strategy score
        strat_score = 5
        strat_just = []
        strat_missing = []
        if info['has_strategy']:
            strat_score += 2
            strat_just.append("Strategy concepts were taught")
        if len(info['topics_discussed']) >= 2:
            strat_score += 2
            strat_just.append("multiple topics covered ({})".format(', '.join(info['topics_discussed'][:3])))
        if not strat_just:
            strat_just.append("Limited strategy instruction documented")
        strat_missing.append("Summary of strategy concepts taught")
        strat_missing.append("Student-specific takeaways")
        
        self.scores['Strategy'] = min(strat_score, 10)
        self.justifications['Strategy'] = ' '.join(strat_just) + "." if strat_just else "Strategy portion documentation is incomplete."
        self.missing_items['Strategy'] = strat_missing
        
        # Clarity score
        clarity_score = 4
        clarity_just = []
        clarity_missing = []
        if info['has_next_session']:
            clarity_score += 2
            clarity_just.append("Next session timing discussed")
        else:
            clarity_missing.append("Confirmed next session date")
        clarity_missing.append("Comprehensive next-steps summary")
        clarity_missing.append("Full list of assignments")
        
        self.scores['Clarity'] = min(clarity_score, 10)
        self.justifications['Clarity'] = ' '.join(clarity_just) + ". However, the session ended without a clear documented recap." if clarity_just else "Session concluded without comprehensive documented next steps."
        self.missing_items['Clarity'] = clarity_missing
        
        # Calculate average
        avg = sum(self.scores.values()) / len(self.scores)
        
        # Determine rating
        if avg >= 8.5:
            rating = 'Strong Session'
        elif avg >= 7.0:
            rating = 'Adequate'
        elif avg >= 5.0:
            rating = 'Needs Improvement'
        else:
            rating = 'Review Required'
        
        self.findings = {
            'info': info,
            'notes_check': notes_check,
            'scores': self.scores,
            'average': round(avg, 1),
            'rating': rating
        }
        return self.findings
    
    def _get_biggest_risk(self):
        """Determine biggest risk based on scores."""
        if self.scores.get('Study Plan', 10) <= 4:
            return "No formal session notes exist - student has no take-home documentation with study plan, exam schedule, weekly checklist, or daily tasks."
        elif self.scores.get('Clarity', 10) <= 4:
            return "Student left session without clear next steps or confirmed follow-up date."
        elif self.scores.get('Preparation', 10) <= 4:
            return "Insufficient baseline assessment may lead to misaligned study recommendations."
        else:
            return "Documentation gaps may impact student's ability to follow study plan independently."
    
    def _get_top_fixes(self):
        """Generate top 3 fixes based on lowest scores."""
        fixes = []
        if self.scores.get('Study Plan', 10) <= 5:
            fixes.append("Create a proper Google Doc with student snapshot, study schedule, FL exam dates, AAMC question pack scheduling, and weekly/daily task breakdown")
        if self.scores.get('Study Plan', 10) <= 6:
            fixes.append("Document the FL exam schedule explicitly (10 FLs: JW FL 1-6 + AAMC exams, with dates for each)")
        if self.missing_items.get('Preparation'):
            fixes.append("Add below-average topic list with specific daily/weekly assignments for weak areas")
        if self.scores.get('Clarity', 10) <= 5:
            fixes.append("Confirm next session date and document clear action items with deadlines")
        if self.scores.get('Strategy', 10) <= 6:
            fixes.append("Document strategy concepts taught during session for student reference")
        return fixes[:3]
    
    def _generate_tutor_feedback(self):
        """Generate detailed tutor feedback."""
        info = self.findings['info']
        
        positives = []
        if info['has_strategy'] and len(info['topics_discussed']) >= 2:
            positives.append(("Strong Content Instruction", "Multiple topics were covered with evident strategy discussion. This demonstrates good session utilization and content expertise."))
        if info['has_adhd'] or info['has_classes']:
            positives.append(("Awareness of Student Context", "You acknowledged the student's personal constraints and circumstances, which builds rapport and trust."))
        if info['transcript_length'] > 30000:
            positives.append(("Thorough Session", "The substantial session length indicates comprehensive coverage rather than rushing through material."))
        if info['has_next_session']:
            positives.append(("Forward Planning", "Discussion of next session timing shows continuity planning."))
        if len(info['topics_discussed']) >= 3:
            positives.append(("Broad Topic Coverage", "You addressed multiple content areas: {}.".format(', '.join(info['topics_discussed'][:4]))))
        
        if not positives:
            positives.append(("Session Conducted", "The tutoring session was completed."))
        
        improvements = []
        if self.scores['Study Plan'] <= 5:
            improvements.append({
                'title': 'Critical: No Session Documentation Created',
                'what': 'The session produced minimal documented notes. No formal notes document exists with structured study plan.',
                'why': 'Student has no reference document for their study plan, exam schedule, or strategies discussed. They cannot follow a structured plan independently.',
                'fix': 'Create a Google Doc immediately using the Notes v2 template. Include: Student Snapshot, Exam Schedule, Weekly Checklist, Week 1 Daily Tasks, Strategy Summary. Share with student AND anastasia@jackwestin.com, michaelmel@jackwestin.com. Budget 10-15 minutes at session end for documentation.'
            })
        
        if self.scores['Study Plan'] <= 6 and self.scores['Study Plan'] > 5:
            improvements.append({
                'title': 'Missing: Structured Exam Schedule',
                'what': 'FL sequencing may have been discussed verbally but specific dates were not documented.',
                'why': 'Student needs clarity on which test to take each week. Without a documented schedule, they may sequence incorrectly.',
                'fix': 'Create a table: Week | Date | Exam | Notes. Be explicit about when to start AAMC materials.'
            })
        
        if self.missing_items.get('Preparation') and len(self.missing_items['Preparation']) > 1:
            improvements.append({
                'title': 'Missing: Below-Average Topic Prioritization',
                'what': 'Weak areas may have been identified through discussion but no prioritized topic list was created in notes.',
                'why': 'Student needs specific topics to focus on. Without this list, they may study inefficiently.',
                'fix': 'Create a "Priority Topics" section organized by MCAT section. Exclude topics covered by live course. Rank by importance.'
            })
        
        if self.scores['Clarity'] <= 5:
            improvements.append({
                'title': 'Incomplete: Next Session Planning',
                'what': 'No specific next session date was confirmed or documented.',
                'why': 'Without a confirmed date, follow-up may slip. Session 1 momentum is critical.',
                'fix': 'Always confirm a specific date before ending Session 1. Document it in notes with planned focus areas. Include "Student to bring: [items]".'
            })
        
        return positives, improvements
    
    def _generate_gap_analysis(self):
        """Generate transcript vs notes gap analysis."""
        info = self.findings['info']
        
        gap_items = [
            ('Test date: ' + info['test_date'], info['test_date'] != 'Not found', 'No'),
            ('Baseline score: ~' + info['baseline_score'], info['baseline_score'] != 'Not found', 'No'),
            ('Target score: ' + info['target_score'], info['target_score'] != 'Not found', 'No'),
            ('Student constraints (classes, accommodations)', info['has_classes'] or info['has_adhd'], 'No'),
            ('Weak areas identified', info['weak_chem'] or info['weak_bio'], 'No'),
            ('Strong areas identified', info['strong_cars'] or info['strong_psych'], 'No'),
            ('FL exam schedule (10 exams: JW FL + AAMC)', True, 'No'),
            ('AAMC question packs/resources scheduling', True, 'No'),
        ]
        
        for topic in info['topics_discussed']:
            gap_items.append((topic + ' strategy', True, 'Partial'))
        
        gap_items.append(('Next session timing', info['has_next_session'], 'No'))
        
        return gap_items
    
    def _generate_notes_v2_clean(self):
        """Generate recommended notes rewrite in clean format."""
        info = self.findings['info']
        session_dt = datetime.strptime(self.session_date, '%Y-%m-%d') if self.session_date else datetime.now()
        
        exam_schedule = []
        for i in range(9):
            exam_date = session_dt + timedelta(days=(i+1)*7 - session_dt.weekday() + 5)
            if i < 3:
                exam_name = "Jack Westin FL {}".format(i+1)
            else:
                exam_name = "AAMC FL {}".format(i-2)
            exam_schedule.append((i+1, exam_date.strftime('%b %d'), exam_name))
        
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        week1_tasks = [
            (days[0], "Session complete. Review foundational concepts from today's discussion"),
            (days[1], "Content review: Focus on primary weak area. Discrete practice: 10-15 questions"),
            (days[2], "Content review: Secondary weak area. Passage practice: 1 passage"),
            (days[3], "Content review: Third topic area. Discrete practice: 10-15 questions"),
            (days[4], "Light review day. Anki cards for memorization items"),
            (days[5], "Full Length Practice Test - Simulate test conditions"),
            (days[6], "FL review with tracker. Identify top 3 new weak areas"),
        ]
        
        notes_v2 = """SESSION 1 NOTES - {student}

Tutor: {tutor}
Date: {date}

________________________________________________________________________________

Student Snapshot

Field               | Value
--------------------|------------------------------------------------------------
Test Date           | {test_date}
Baseline Score      | ~{baseline}
Target Score        | {target}+
Accommodations      | {accommodations}
Current Commitments | {commitments}

________________________________________________________________________________

Priorities (Below-Average Topics)

Excluding topics covered by live course:

Section     | Priority Topics
------------|------------------------------------------------------------------
Chem/Phys   | {chem_topics}
Bio/Biochem | {bio_topics}

Strengths: {strengths}

________________________________________________________________________________

Practice Exam Schedule

Week | Date   | Exam              | Notes
-----|--------|-------------------|--------------------------------------
""".format(
            student=self.student_name.upper(),
            tutor=self.tutor_name,
            date=self.session_date,
            test_date=info['test_date'] if info['test_date'] != 'Not found' else '[CONFIRM WITH STUDENT]',
            baseline=info['baseline_score'] if info['baseline_score'] != 'Not found' else '[ADD SCORE]',
            target=info['target_score'] if info['target_score'] != 'Not found' else '510',
            accommodations='ADHD accommodations (stop-the-clock breaks)' if info['has_adhd'] else 'None documented',
            commitments='School/coursework' if info['has_classes'] else 'Work' if info['has_work'] else '[CONFIRM]',
            chem_topics='Physics fundamentals, acid-base equilibrium, general chemistry' if info['weak_chem'] else '[IDENTIFY WEAK TOPICS]',
            bio_topics='Enzyme kinetics, cellular processes' if info['weak_bio'] else '[IDENTIFY WEAK TOPICS]',
            strengths=('CARS' if info['strong_cars'] else '') + (', Psych/Soc' if info['strong_psych'] else '') or '[IDENTIFY STRENGTHS]'
        )
        
        for week, date, exam in exam_schedule:
            notes_v2 += "{:<4} | {:<6} | {:<17} |\n".format(week, date, exam)
        
        notes_v2 += """
________________________________________________________________________________

AAMC Question Packs/Resources Plan

(Only applicable if student has these resources — check student notes sheet)
Resources list: Bio QP Vol 1 & 2, Chem QP, Physics QP, CARS QP Vol 1 & 2,
Section Bank, Official Prep Hub Question Bank, CARS Diagnostic Tool, Flashcards

- Section Banks: Integrate during AAMC FL phase
- Q-Packs: Use for supplemental topic review
- Flashcards: Ongoing throughout study period
- Deadline: All AAMC materials completed by test day minus 1

________________________________________________________________________________

Weekly Checklist (Ongoing)

[ ] Complete 1 full-length practice exam
[ ] Review FL thoroughly using tracker
[ ] 2-3 hours daily content review
[ ] Daily CARS passage practice
[ ] Course assignments
[ ] Anki cards for weak content areas

________________________________________________________________________________

Week 1 Daily Tasks

Day  | Task
-----|----------------------------------------------------------------------
"""
        for day, task in week1_tasks:
            notes_v2 += "{:<4} | {}\n".format(day, task)
        
        notes_v2 += """
________________________________________________________________________________

Strategy Focus (From Today's Session)

"""
        for i, topic in enumerate(info['topics_discussed'], 1):
            notes_v2 += "{}. {}\n   - [Add key points from session discussion]\n   - [Add student-specific takeaways]\n\n".format(i, topic)
        
        if not info['topics_discussed']:
            notes_v2 += "1. [Topic 1]\n   - [Add key points]\n\n2. [Topic 2]\n   - [Add key points]\n\n"
        
        notes_v2 += """________________________________________________________________________________

Next Session Plan

- Tentative Date: [CONFIRM DATE - suggest 2-3 weeks out]
- Focus: Review FL performance, adjust study plan, content check-in
- Student to bring: Top 3-5 questions from FL review

________________________________________________________________________________

Tutor Contact

- Email: {tutor_email} (available for quick concept questions)

________________________________________________________________________________

Document shared with: anastasia@jackwestin.com, michaelmel@jackwestin.com
""".format(tutor_email=self.tutor_name.lower().replace(' ', '') + '@jackwestin.com')
        
        return notes_v2
    
    def generate_report(self):
        """Generate the full comprehensive grading report in clean format."""
        if not self.findings:
            self.grade()
        
        f = self.findings
        info = f['info']
        notes_check = f['notes_check']
        
        positives, improvements = self._generate_tutor_feedback()
        gap_items = self._generate_gap_analysis()
        notes_v2 = self._generate_notes_v2_clean()
        
        sep = "________________________________________________________________________________"
        
        report = """SESSION 1 GRADING REPORT

Student: {student}
Tutor: {tutor}
Session Date: {date}
Test Date: {test_date}
Graded By: JW Session Notes Grader (Agent)

{sep}

SECTION 1: QUICK VERDICT

Overall Rating: {rating}
Biggest Risk: {risk}

Top 3 Fixes

""".format(
            student=self.student_name,
            tutor=self.tutor_name,
            date=self.session_date,
            test_date=info['test_date'],
            rating=f['rating'].upper(),
            risk=self._get_biggest_risk(),
            sep=sep
        )
        
        for i, fix in enumerate(self._get_top_fixes(), 1):
            report += "{}. {}\n".format(i, fix)
        
        report += """
{sep}

SECTION 2: CATEGORY SCORES (EQUAL WEIGHT, 1-10 EACH)

A. Preparation and Planning Readiness

Score: {prep}/10

Justification:
{prep_just}

Missing from Notes:
""".format(
            prep=self.scores['Preparation'],
            prep_just=self.justifications['Preparation'],
            sep=sep
        )
        for item in self.missing_items['Preparation']:
            report += "- {}\n".format(item)
        
        report += """
{sep}

B. Study Plan Construction Quality

Score: {plan}/10

Justification:
{plan_just}

Missing from Notes:
""".format(
            plan=self.scores['Study Plan'],
            plan_just=self.justifications['Study Plan'],
            sep=sep
        )
        for item in self.missing_items['Study Plan']:
            report += "- {}\n".format(item)
        
        report += """
{sep}

C. Personalization and Load Calibration

Score: {personal}/10

Justification:
{personal_just}

Missing from Notes:
""".format(
            personal=self.scores['Personalization'],
            personal_just=self.justifications['Personalization'],
            sep=sep
        )
        for item in self.missing_items['Personalization']:
            report += "- {}\n".format(item)
        
        report += """
{sep}

D. Strategy Portion Execution

Score: {strategy}/10

Justification:
{strategy_just}

Missing from Notes:
""".format(
            strategy=self.scores['Strategy'],
            strategy_just=self.justifications['Strategy'],
            sep=sep
        )
        for item in self.missing_items['Strategy']:
            report += "- {}\n".format(item)
        
        report += """
{sep}

E. Clarity and Student Buy-In

Score: {clarity}/10

Justification:
{clarity_just}

Missing from Notes:
""".format(
            clarity=self.scores['Clarity'],
            clarity_just=self.justifications['Clarity'],
            sep=sep
        )
        for item in self.missing_items['Clarity']:
            report += "- {}\n".format(item)
        
        report += """
{sep}

SECTION 3: SOP COMPLIANCE CHECKLIST (NOTES-BASED)

SOP Item                                          | Present? | Evidence
--------------------------------------------------|----------|--------------------------------------------------
Full-Length Exam schedule (10 FLs)                | {fl_status:8} | {fl_ev}
AAMC Question Packs/Resources                     | {qp_status:8} | {qp_ev}
Below-average topics (excluding course-covered)   | {topics_status:8} | {topics_ev}
Weekly checklist                                  | {weekly_status:8} | {weekly_ev}
Daily tasks for Week 1                            | {daily_status:8} | {daily_ev}
Strategy portion notes                            | {strat_status:8} | {strat_ev}
Tentative next session date                       | {next_status:8} | {next_ev}
Google Doc shared                                 | {doc_status:8} | {doc_ev}
Baseline score documented                         | {base_status:8} | {base_ev}

Compliance Summary: {compliant} fully compliant, {partial} partial, {missing} missing

{sep}

SECTION 4: TRANSCRIPT VS. NOTES GAP ANALYSIS

What Was Discussed in Transcript (Should Have Been in Notes)

Topic Discussed                                           | In Notes?
----------------------------------------------------------|----------
""".format(
            fl_status=notes_check['fl_exam_schedule']['status'],
            fl_ev=notes_check['fl_exam_schedule']['evidence'][:50],
            qp_status=notes_check['aamc_question_packs']['status'],
            qp_ev=notes_check['aamc_question_packs']['evidence'][:50],
            topics_status=notes_check['below_avg_topics']['status'],
            topics_ev=notes_check['below_avg_topics']['evidence'][:50],
            weekly_status=notes_check['weekly_checklist']['status'],
            weekly_ev=notes_check['weekly_checklist']['evidence'][:50],
            daily_status=notes_check['daily_tasks']['status'],
            daily_ev=notes_check['daily_tasks']['evidence'][:50],
            strat_status=notes_check['strategy_notes']['status'],
            strat_ev=notes_check['strategy_notes']['evidence'][:50],
            next_status=notes_check['next_session']['status'],
            next_ev=notes_check['next_session']['evidence'][:50],
            doc_status=notes_check['google_doc_shared']['status'],
            doc_ev=notes_check['google_doc_shared']['evidence'][:50],
            base_status=notes_check['baseline_documented']['status'],
            base_ev=notes_check['baseline_documented']['evidence'][:50],
            compliant=sum(1 for v in notes_check.values() if v['status'] == 'Yes'),
            partial=sum(1 for v in notes_check.values() if v['status'] == 'Partial'),
            missing=sum(1 for v in notes_check.values() if v['status'] == 'No'),
            sep=sep
        )
        
        for topic, discussed, in_notes in gap_items:
            if discussed:
                report += "{:57} | {}\n".format(topic[:57], in_notes)
        
        report += """
{sep}

SECTION 5: RECOMMENDED NOTES REWRITE (NOTES V2)

Given that multiple critical SOP items are missing from notes, below is a recommended rewrite.

{sep}

{notes_v2}

{sep}

SECTION 6: TUTOR FEEDBACK

What You Did Well

""".format(notes_v2=notes_v2, sep=sep)
        
        for i, (title, desc) in enumerate(positives, 1):
            report += "{}. {}\n   {}\n\n".format(i, title, desc)
        
        report += """{sep}

Areas for Improvement

""".format(sep=sep)
        
        for i, imp in enumerate(improvements, 1):
            report += """{}. {}

   What happened: {}

   Why it matters: {}

   How to fix: {}

""".format(i, imp['title'], imp['what'], imp['why'], imp['fix'])
        
        report += """{sep}

Priority Actions Before Next Session

[ ] Immediate: Create and share Session 1 Google Doc with full study plan (use Notes v2 template above)
[ ] Within 24 hours: Email student to confirm next session date and share the document
[ ] Ongoing: Add "Documentation" as a recurring 10-min block at end of each session

{sep}

Coaching Note for {tutor}

Your instructional quality during the session appears solid based on the transcript content. The gap is in documentation. Think of the notes as the "product" the student takes home; the conversation is valuable, but the notes are what they'll reference daily.

A simple template can make this fast: spend the last 10 minutes of each session filling in a shared Google Doc together with the student. This also creates buy-in since they see exactly what's expected.

{sep}

FINAL SCORE SUMMARY

Category                                | Score
----------------------------------------|-------
Preparation & Planning Readiness        | {prep}/10
Study Plan Construction Quality         | {plan}/10
Personalization & Load Calibration      | {personal}/10
Strategy Portion Execution              | {strategy}/10
Clarity & Student Buy-In                | {clarity}/10
----------------------------------------|-------
Average                                 | {avg}/10

{sep}

OVERALL ASSESSMENT: {rating}

Summary:
{summary}

Recommended Actions:
1. Tutor should immediately create and share a comprehensive Session 1 Google Doc (see Notes v2 above)
2. Confirm next session date in writing
3. Future sessions should include 5-10 minutes at end for documentation review with student

{sep}

Graded by: JW Session Notes Grader Agent
Grading Agent Version: 1.0
Reference Documents: first_session_sop_agent.md, grading_first_session_agent.md
""".format(
            tutor=self.tutor_name.split()[0] if self.tutor_name else 'Tutor',
            prep=self.scores['Preparation'],
            plan=self.scores['Study Plan'],
            personal=self.scores['Personalization'],
            strategy=self.scores['Strategy'],
            clarity=self.scores['Clarity'],
            avg=f['average'],
            rating=f['rating'].upper(),
            summary=self._generate_summary(),
            sep=sep
        )
        
        return report
    
    def _generate_summary(self):
        """Generate overall summary."""
        avg = self.findings['average']
        if avg >= 8.5:
            return "Excellent session with comprehensive documentation. All major SOP items are addressed and the student has clear direction."
        elif avg >= 7.0:
            return "Good session with adequate documentation. Minor improvements recommended for completeness."
        elif avg >= 5.0:
            return "The tutoring session content appears solid based on transcript analysis. However, the session documentation is deficient. The student has minimal take-home artifacts: limited study schedule documentation, incomplete exam calendar, and sparse task lists. Without proper notes, the student cannot effectively reference what was discussed or follow a structured plan. This creates risk for student outcomes and does not fully meet SOP requirements."
        else:
            return "Significant documentation gaps identified. The session requires immediate follow-up to ensure the student has necessary study materials and clear direction. Priority action: Create comprehensive session notes immediately."


def send_email(to_emails, subject, body):
    """Send email using SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = ', '.join(to_emails)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_emails, msg.as_string())
        return True
    except Exception as e:
        print("Email error: " + str(e))
        return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            
            required = ['student_name', 'tutor_name', 'tutor_email', 'session_date', 'transcript']
            for field in required:
                if not data.get(field):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Missing: ' + field}).encode())
                    return
            
            grader = SessionGrader(
                transcript=data['transcript'],
                student_name=data['student_name'],
                tutor_name=data['tutor_name'],
                session_date=data['session_date'],
                student_notes=data.get('student_notes', ''),
                sop_study_schedule=data.get('sop_study_schedule', 'no'),
                sop_question_packs=data.get('sop_question_packs', 'no'),
                sop_full_length_exams=data.get('sop_full_length_exams', 'no'),
            )

            findings = grader.grade()
            report = grader.generate_report()

            # Email sending disabled — drafts are generated but not sent

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'scores': findings['scores'],
                'average_score': findings['average'],
                'overall_rating': findings['rating'],
                'email_sent': False,
                'report': report
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'endpoint': '/api/grade', 'method': 'POST'}).encode())
