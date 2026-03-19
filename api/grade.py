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

# Hard-coded director recipients — all grading reports go to these four
DIRECTOR_EMAILS = [
    "anastasia@jackwestin.com",
    "carlb@jackwestin.com",
    "Molly@jackwestin.com",
    "adamrs@jackwestin.com",
]


class SessionGrader:
    """Grader for Session 1 tutoring notes using 4-category 135-point rubric."""

    def __init__(self, transcript, student_name, tutor_name, session_date, student_notes='',
                 sop_study_schedule='no', sop_question_packs='no', sop_full_length_exams='no',
                 course_type='515', session_number='1'):
        self.transcript = transcript
        self.student_name = student_name
        self.tutor_name = tutor_name
        self.session_date = session_date
        self.student_notes = student_notes or ''
        self.sop_study_schedule = (sop_study_schedule or 'no').lower()
        self.sop_question_packs = (sop_question_packs or 'no').lower()
        self.sop_full_length_exams = (sop_full_length_exams or 'no').lower()
        self.course_type = (course_type or '515').lower()
        self.session_number = str(session_number or '1')
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
        """Check what rubric items are present in the notes/transcript.

        Returns a dict keyed by the new rubric score keys with status and evidence.
        """
        text = self.transcript.lower()
        notes_lower = (self.student_notes or '').lower()
        combined = text + ' ' + notes_lower

        # AAMC dual-source rule
        student_doc_confirms_aamc = self._check_student_notes_aamc()

        # March 5 placeholder detection for FL exams
        total_dates, march5_count = self._count_march5_exams(combined)

        checks = {}

        # --- A1: Session Structure & Timing (10 pts) ---
        has_intro = any(w in text for w in ['introduce', 'introduction', 'welcome', 'nice to meet', 'how are you'])
        has_agenda = any(w in text for w in ['agenda', 'today we', 'plan for today', 'going to cover', 'outline'])
        has_timing = any(w in text for w in ['minutes', 'hour', 'time', 'clock', 'wrap up', 'end of session'])
        checks['a1_structure'] = {
            'status': 'Yes' if (has_intro and has_agenda) else ('Partial' if (has_intro or has_agenda) else 'No'),
            'evidence': 'Session structure with intro and agenda detected' if (has_intro and has_agenda)
                        else 'Partial session structure detected' if (has_intro or has_agenda)
                        else '(Not documented)',
            'max_pts': 10
        }

        # --- A2: Study Schedule & Exam Planning (14 pts total) ---
        # A2 base: study schedule (via SOP verification or transcript)
        schedule_confirmed = self.sop_study_schedule == 'yes'
        schedule_partial = self.sop_study_schedule == 'partial'
        has_schedule_ref = any(w in text for w in ['study schedule', 'study plan', 'weekly schedule', 'daily schedule'])
        checks['a2_schedule'] = {
            'status': 'Yes' if (schedule_confirmed or has_schedule_ref) else ('Partial' if schedule_partial else 'No'),
            'evidence': 'Study schedule confirmed via SOP verification (YES)' if schedule_confirmed
                        else 'Study schedule referenced in transcript' if has_schedule_ref
                        else 'Study schedule partially confirmed via SOP verification (PARTIAL)' if schedule_partial
                        else '(Not documented)',
            'max_pts': 4
        }

        # A2 FL exams (proportional scoring)
        fl_keywords = ['full length', 'full-length', 'jw fl', 'jack westin fl', 'practice exam', 'aamc fl']
        has_fl_ref = ('fl' in text and any(w in text for w in ['schedule', 'week', 'saturday', 'date'])) or any(kw in text for kw in fl_keywords)
        fl_confirmed_sop = self.sop_full_length_exams == 'yes'
        fl_partial_sop = self.sop_full_length_exams == 'partial'

        if fl_confirmed_sop:
            checks['a2_fl_exams'] = {'status': 'Yes', 'evidence': 'FL exams confirmed via SOP verification (YES)', 'max_pts': 6}
        elif has_fl_ref:
            if march5_count > 0 and total_dates > 0 and march5_count >= total_dates * 0.7:
                checks['a2_fl_exams'] = {'status': 'No', 'evidence': 'Exam dates use default March 5th placeholder — not actually scheduled', 'max_pts': 6}
            elif march5_count > 0 and total_dates > march5_count:
                checks['a2_fl_exams'] = {'status': 'Partial', 'evidence': 'Some exams scheduled but {} of {} dates are March 5th placeholder'.format(march5_count, total_dates), 'max_pts': 6}
            else:
                checks['a2_fl_exams'] = {'status': 'Partial', 'evidence': 'FL exam scheduling discussed but dates not fully documented', 'max_pts': 6}
        elif fl_partial_sop:
            checks['a2_fl_exams'] = {'status': 'Partial', 'evidence': 'FL exams partially confirmed via SOP verification (PARTIAL)', 'max_pts': 6}
        else:
            checks['a2_fl_exams'] = {'status': 'No', 'evidence': '(Not documented)', 'max_pts': 6}

        # A2 AAMC question packs (binary)
        qpack_keywords = ['question pack', 'q-pack', 'qpack', 'section bank', 'flashcard', 'official prep', 'diagnostic tool']
        has_no_aamc = 'no aamc' in text or "doesn't have aamc" in text or 'does not have aamc' in text or "don't have aamc" in text
        aamc_confirmed_sop = self.sop_question_packs == 'yes'
        aamc_partial_sop = self.sop_question_packs == 'partial'

        if has_no_aamc:
            checks['a2_aamc'] = {'status': 'Yes', 'evidence': 'Student has no AAMC question packs — full credit', 'max_pts': 4}
        elif student_doc_confirms_aamc:
            checks['a2_aamc'] = {'status': 'Yes', 'evidence': 'Student notes document confirms AAMC materials assigned/scheduled', 'max_pts': 4}
        elif aamc_confirmed_sop:
            checks['a2_aamc'] = {'status': 'Yes', 'evidence': 'AAMC packs confirmed via SOP verification (YES)', 'max_pts': 4}
        elif any(kw in text for kw in qpack_keywords):
            checks['a2_aamc'] = {'status': 'Partial', 'evidence': 'AAMC question packs/resources mentioned', 'max_pts': 4}
        elif 'aamc' in text and not any(kw in text for kw in ['exam', 'full length', 'full-length']):
            checks['a2_aamc'] = {'status': 'Partial', 'evidence': 'AAMC materials referenced (likely question packs)', 'max_pts': 4}
        elif aamc_partial_sop:
            checks['a2_aamc'] = {'status': 'Partial', 'evidence': 'AAMC packs partially confirmed via SOP verification (PARTIAL)', 'max_pts': 4}
        else:
            checks['a2_aamc'] = {'status': 'No', 'evidence': '(Not documented)', 'max_pts': 4}

        # --- A3: Pre/Post-Session Tasks (12 pts) ---
        has_presession = any(w in text for w in ['before session', 'pre-session', 'prepared', 'reviewed before', 'looked at'])
        checks['a3_presession'] = {
            'status': 'Yes' if has_presession else 'No',
            'evidence': 'Pre-session preparation referenced' if has_presession else '(Not documented)',
            'max_pts': 3
        }

        has_survey = any(w in text for w in ['survey', 'questionnaire', 'intake form', 'feedback form', 'pre-session form'])
        checks['a3_survey'] = {
            'status': 'Yes' if has_survey else 'No',
            'evidence': 'Survey/intake form referenced' if has_survey else '(Not documented)',
            'max_pts': 3
        }

        has_postsession = any(w in text for w in ['notes', 'document', 'write up', 'summary', 'session notes', 'recap'])
        checks['a3_postsession_notes'] = {
            'status': 'Yes' if has_postsession else 'No',
            'evidence': 'Post-session notes/documentation referenced' if has_postsession else '(Not documented)',
            'max_pts': 3
        }

        has_shared = any(w in text for w in ['shared', 'share with', 'sent to', 'emailed', 'google doc'])
        checks['a3_shared'] = {
            'status': 'Yes' if has_shared else 'No',
            'evidence': 'Document sharing referenced' if has_shared else '(Not documented)',
            'max_pts': 3
        }

        # --- A4: Session-Specific Requirements (14 pts) ---
        has_baseline = any(w in text for w in ['baseline', 'diagnostic', 'starting score', 'initial score'])
        has_test_date = any(w in text for w in ['test date', 'exam date', 'mcat date', 'testing date'])
        has_weak_areas = any(w in text for w in ['weak', 'below', 'struggle', 'hard', 'difficult', 'improve'])
        has_commitments = any(w in text for w in ['class', 'school', 'work', 'job', 'schedule', 'busy', 'commitment'])
        has_next_session_plan = any(w in text for w in ['next session', 'next week', 'follow up', 'follow-up'])
        session_specific_count = sum([has_baseline, has_test_date, has_weak_areas, has_commitments, has_next_session_plan])
        checks['a4_specific'] = {
            'status': 'Yes' if session_specific_count >= 4 else ('Partial' if session_specific_count >= 2 else 'No'),
            'evidence': 'Session-specific requirements addressed ({}/5 items found)'.format(session_specific_count) if session_specific_count > 0
                        else '(Not documented)',
            'max_pts': 14
        }

        # --- B1: Socratic Method (15 pts) ---
        probing_keywords = ['what do you think', 'why do you think', 'how would you', 'can you explain', 'what happens if', 'tell me', 'walk me through']
        probing_count = sum(1 for kw in probing_keywords if kw in text)
        checks['b1_probing'] = {
            'status': 'Yes' if probing_count >= 3 else ('Partial' if probing_count >= 1 else 'No'),
            'evidence': '{} probing question patterns detected'.format(probing_count) if probing_count > 0 else '(Not documented)',
            'max_pts': 5
        }

        student_talk_keywords = ['student:', 'student says', 'i think', 'my answer', 'i would say', 'because i']
        student_talk_count = sum(1 for kw in student_talk_keywords if kw in text)
        checks['b1_student_talks'] = {
            'status': 'Yes' if student_talk_count >= 3 else ('Partial' if student_talk_count >= 1 else 'No'),
            'evidence': '{} student-talk indicators detected'.format(student_talk_count) if student_talk_count > 0 else '(Not documented)',
            'max_pts': 5
        }

        remap_keywords = ['let me just tell you', 'the answer is', 'you should memorize', 'just remember that']
        has_remap = any(kw in text for kw in remap_keywords)
        checks['b1_no_remap'] = {
            'status': 'No' if has_remap else 'Yes',
            'evidence': 'Direct answer-giving detected (should use Socratic method)' if has_remap else 'No direct answer-giving detected',
            'max_pts': 5
        }

        # --- B2: Weakness Identification (15 pts) ---
        reason_keywords = ['because', 'the reason', 'root cause', 'underlying', 'fundamental issue', 'core problem']
        reason_count = sum(1 for kw in reason_keywords if kw in text)
        checks['b2_identifies_reasons'] = {
            'status': 'Yes' if reason_count >= 2 else ('Partial' if reason_count >= 1 else 'No'),
            'evidence': '{} reasoning/root-cause indicators detected'.format(reason_count) if reason_count > 0 else '(Not documented)',
            'max_pts': 5
        }

        excuse_keywords = ['it\'s okay', "don't worry about it", 'that\'s fine', 'no big deal', 'everyone struggles']
        has_excuses = any(kw in text for kw in excuse_keywords)
        checks['b2_no_excuses'] = {
            'status': 'No' if has_excuses else 'Yes',
            'evidence': 'Excuse-making language detected' if has_excuses else 'No excuse-making language detected',
            'max_pts': 5
        }

        action_keywords = ['practice', 'drill', 'review', 'focus on', 'work on', 'try doing', 'assignment', 'homework', 'task']
        action_count = sum(1 for kw in action_keywords if kw in text)
        checks['b2_actionable'] = {
            'status': 'Yes' if action_count >= 3 else ('Partial' if action_count >= 1 else 'No'),
            'evidence': '{} actionable recommendation indicators detected'.format(action_count) if action_count > 0 else '(Not documented)',
            'max_pts': 5
        }

        # --- B3: Passage Practice (10 pts) ---
        passage_q_keywords = ['passage', 'question 1', 'question 2', 'question 3', 'first question', 'second question', 'third question', 'next question']
        passage_q_count = sum(1 for kw in passage_q_keywords if kw in text)
        checks['b3_three_qs'] = {
            'status': 'Yes' if passage_q_count >= 3 else ('Partial' if passage_q_count >= 1 else 'No'),
            'evidence': '{} passage/question references detected'.format(passage_q_count) if passage_q_count > 0 else '(Not documented)',
            'max_pts': 4
        }

        teach_keywords = ['explain to me', 'teach it back', 'in your own words', 'walk me through', 'how would you explain']
        teach_count = sum(1 for kw in teach_keywords if kw in text)
        checks['b3_student_teaches'] = {
            'status': 'Yes' if teach_count >= 1 else 'No',
            'evidence': '{} teach-back indicators detected'.format(teach_count) if teach_count > 0 else '(Not documented)',
            'max_pts': 3
        }

        feedback_keywords = ['paragraph', 'feedback', 'here is what', 'your approach', 'you did well', 'next time try']
        feedback_count = sum(1 for kw in feedback_keywords if kw in text)
        checks['b3_paragraph_feedback'] = {
            'status': 'Yes' if feedback_count >= 2 else ('Partial' if feedback_count >= 1 else 'No'),
            'evidence': '{} feedback indicators detected'.format(feedback_count) if feedback_count > 0 else '(Not documented)',
            'max_pts': 3
        }

        # --- B4: Student Engagement (10 pts) ---
        takeaway_keywords = ['takeaway', 'take away', 'key point', 'remember that', 'main lesson', 'biggest thing']
        takeaway_count = sum(1 for kw in takeaway_keywords if kw in text)
        checks['b4_takeaways'] = {
            'status': 'Yes' if takeaway_count >= 1 else 'No',
            'evidence': '{} takeaway indicators detected'.format(takeaway_count) if takeaway_count > 0 else '(Not documented)',
            'max_pts': 4
        }

        question_keywords = ['any questions', 'do you have questions', 'does that make sense', 'anything unclear', 'want to ask']
        question_count = sum(1 for kw in question_keywords if kw in text)
        checks['b4_questions'] = {
            'status': 'Yes' if question_count >= 2 else ('Partial' if question_count >= 1 else 'No'),
            'evidence': '{} question-check indicators detected'.format(question_count) if question_count > 0 else '(Not documented)',
            'max_pts': 3
        }

        timing_keywords = ['on time', 'started on time', 'minutes left', 'running over', 'wrap up']
        timing_count = sum(1 for kw in timing_keywords if kw in text)
        checks['b4_timing_accuracy'] = {
            'status': 'Yes' if timing_count >= 1 else 'No',
            'evidence': '{} timing/punctuality indicators detected'.format(timing_count) if timing_count > 0 else '(Not documented)',
            'max_pts': 3
        }

        # --- C: Notes & Documentation (20 pts, 6 binary items) ---
        has_template_named = bool(re.search(r'session\s*1?\s*notes|notes?\s*v2|student\s+notes', notes_lower)) or bool(re.search(r'session\s*1?\s*notes|notes?\s*v2', text))
        checks['c_template_named'] = {
            'status': 'Yes' if has_template_named else 'No',
            'evidence': 'Named session notes template detected' if has_template_named else '(Not documented)',
            'max_pts': 3
        }

        has_overview = any(w in notes_lower for w in ['overview', 'snapshot', 'student info', 'student profile', 'baseline'])
        checks['c_overview_tab'] = {
            'status': 'Yes' if has_overview else 'No',
            'evidence': 'Overview/snapshot section detected in notes' if has_overview else '(Not documented)',
            'max_pts': 3
        }

        has_detailed_notes = len(notes_lower) > 200 and any(w in notes_lower for w in ['session', 'discussed', 'covered', 'topic', 'strategy', 'review'])
        checks['c_session_notes_detailed'] = {
            'status': 'Yes' if has_detailed_notes else 'No',
            'evidence': 'Detailed session notes detected ({} chars)'.format(len(notes_lower)) if has_detailed_notes else '(Not documented)',
            'max_pts': 5
        }

        has_exam_progress = any(w in notes_lower for w in ['fl', 'full length', 'full-length', 'exam progress', 'score track', 'practice test'])
        checks['c_exam_progress'] = {
            'status': 'Yes' if has_exam_progress else 'No',
            'evidence': 'Exam progress tracking detected in notes' if has_exam_progress else '(Not documented)',
            'max_pts': 3
        }

        has_next_steps = any(w in notes_lower for w in ['next step', 'next session', 'action item', 'homework', 'assignment', 'to do', 'todo', 'follow up', 'follow-up'])
        checks['c_next_steps_written'] = {
            'status': 'Yes' if has_next_steps else 'No',
            'evidence': 'Next steps/action items detected in notes' if has_next_steps else '(Not documented)',
            'max_pts': 3
        }

        has_activity = any(w in notes_lower for w in ['activity', 'tracking', 'log', 'daily task', 'weekly', 'checklist'])
        checks['c_activity_tracking'] = {
            'status': 'Yes' if has_activity else 'No',
            'evidence': 'Activity tracking detected in notes' if has_activity else '(Not documented)',
            'max_pts': 3
        }

        # --- D: Professionalism (15 pts, 5 binary items) ---
        has_good_demeanor = not any(w in text for w in ['rude', 'frustrated', 'annoyed', 'impatient', 'condescending'])
        checks['d_demeanor'] = {
            'status': 'Yes' if has_good_demeanor else 'No',
            'evidence': 'Professional demeanor maintained' if has_good_demeanor else 'Unprofessional language detected',
            'max_pts': 3
        }

        guarantee_keywords = ['guarantee', 'i promise you', 'you will definitely', 'for sure you will', '100% you will']
        has_guarantees = any(kw in text for kw in guarantee_keywords)
        checks['d_no_guarantees'] = {
            'status': 'No' if has_guarantees else 'Yes',
            'evidence': 'Score guarantees detected' if has_guarantees else 'No score guarantees made',
            'max_pts': 3
        }

        improper_channels = ['personal email', 'text me', 'call me on my cell', 'my personal number', 'instagram', 'snapchat']
        has_improper = any(kw in text for kw in improper_channels)
        checks['d_proper_channels'] = {
            'status': 'No' if has_improper else 'Yes',
            'evidence': 'Improper communication channels suggested' if has_improper else 'Proper communication channels used',
            'max_pts': 3
        }

        # On-time: default to Yes unless explicitly late
        late_keywords = ['sorry i\'m late', 'running late', 'apologize for the delay', 'started late']
        was_late = any(kw in text for kw in late_keywords)
        checks['d_on_time'] = {
            'status': 'No' if was_late else 'Yes',
            'evidence': 'Late start detected' if was_late else 'No late start detected',
            'max_pts': 3
        }

        unapproved_platforms = ['discord', 'whatsapp', 'telegram', 'facebook messenger', 'skype']
        has_unapproved = any(kw in text for kw in unapproved_platforms)
        checks['d_approved_platforms'] = {
            'status': 'No' if has_unapproved else 'Yes',
            'evidence': 'Unapproved platform referenced' if has_unapproved else 'Approved platforms used',
            'max_pts': 3
        }

        return checks

    def grade(self):
        """Perform grading using the 4-category 135-point rubric."""
        if self.course_type == 'cars':
            return self._grade_cars()
        info = self.extract_info()
        notes_check = self.check_notes_present()

        # --- Score each item ---

        # A1: Session Structure & Timing (10 pts) — binary
        if notes_check['a1_structure']['status'] == 'Yes':
            self.scores['a1_structure'] = 10
        elif notes_check['a1_structure']['status'] == 'Partial':
            self.scores['a1_structure'] = 5
        else:
            self.scores['a1_structure'] = 0

        # A2: Study Schedule (4 pts) — binary
        if notes_check['a2_schedule']['status'] == 'Yes':
            self.scores['a2_schedule'] = 4
        elif notes_check['a2_schedule']['status'] == 'Partial':
            self.scores['a2_schedule'] = 2
        else:
            self.scores['a2_schedule'] = 0

        # A2: FL Exams (6 pts) — proportional: SOP verification overrides "No"
        fl_status = notes_check['a2_fl_exams']['status']
        if fl_status == 'Yes':
            self.scores['a2_fl_exams'] = 6
        elif fl_status == 'Partial':
            # Proportional: if some exams scheduled vs placeholder
            combined = self.transcript.lower() + ' ' + (self.student_notes or '').lower()
            total_dates, march5_count = self._count_march5_exams(combined)
            if total_dates > 0 and total_dates > march5_count:
                scheduled_ratio = (total_dates - march5_count) / max(total_dates, 1)
                self.scores['a2_fl_exams'] = max(1, round(6 * scheduled_ratio))
            else:
                self.scores['a2_fl_exams'] = 3  # generic partial
        else:
            self.scores['a2_fl_exams'] = 0

        # A2: AAMC (4 pts) — binary
        if notes_check['a2_aamc']['status'] == 'Yes':
            self.scores['a2_aamc'] = 4
        elif notes_check['a2_aamc']['status'] == 'Partial':
            self.scores['a2_aamc'] = 2
        else:
            self.scores['a2_aamc'] = 0

        # A3: Pre-session tasks (3 pts) — binary
        self.scores['a3_presession'] = 3 if notes_check['a3_presession']['status'] == 'Yes' else 0

        # A3: Survey (3 pts) — binary
        self.scores['a3_survey'] = 3 if notes_check['a3_survey']['status'] == 'Yes' else 0

        # A3: Post-session notes (3 pts) — binary
        self.scores['a3_postsession_notes'] = 3 if notes_check['a3_postsession_notes']['status'] == 'Yes' else 0

        # A3: Shared (3 pts) — binary
        self.scores['a3_shared'] = 3 if notes_check['a3_shared']['status'] == 'Yes' else 0

        # A4: Session-Specific Requirements (14 pts) — proportional based on items found
        a4_status = notes_check['a4_specific']['status']
        if a4_status == 'Yes':
            self.scores['a4_specific'] = 14
        elif a4_status == 'Partial':
            self.scores['a4_specific'] = 7
        else:
            self.scores['a4_specific'] = 0

        # B1: Probing questions (5 pts) — binary
        self.scores['b1_probing'] = 5 if notes_check['b1_probing']['status'] == 'Yes' else (2 if notes_check['b1_probing']['status'] == 'Partial' else 0)

        # B1: Student talks (5 pts) — binary
        self.scores['b1_student_talks'] = 5 if notes_check['b1_student_talks']['status'] == 'Yes' else (2 if notes_check['b1_student_talks']['status'] == 'Partial' else 0)

        # B1: No remapping (5 pts) — binary (full if no bad behavior)
        self.scores['b1_no_remap'] = 5 if notes_check['b1_no_remap']['status'] == 'Yes' else 0

        # B2: Identifies reasons (5 pts)
        self.scores['b2_identifies_reasons'] = 5 if notes_check['b2_identifies_reasons']['status'] == 'Yes' else (2 if notes_check['b2_identifies_reasons']['status'] == 'Partial' else 0)

        # B2: No excuses (5 pts) — binary
        self.scores['b2_no_excuses'] = 5 if notes_check['b2_no_excuses']['status'] == 'Yes' else 0

        # B2: Actionable (5 pts)
        self.scores['b2_actionable'] = 5 if notes_check['b2_actionable']['status'] == 'Yes' else (2 if notes_check['b2_actionable']['status'] == 'Partial' else 0)

        # B3: Three questions (4 pts)
        self.scores['b3_three_qs'] = 4 if notes_check['b3_three_qs']['status'] == 'Yes' else (2 if notes_check['b3_three_qs']['status'] == 'Partial' else 0)

        # B3: Student teaches (3 pts) — binary
        self.scores['b3_student_teaches'] = 3 if notes_check['b3_student_teaches']['status'] == 'Yes' else 0

        # B3: Paragraph feedback (3 pts)
        self.scores['b3_paragraph_feedback'] = 3 if notes_check['b3_paragraph_feedback']['status'] == 'Yes' else (1 if notes_check['b3_paragraph_feedback']['status'] == 'Partial' else 0)

        # B4: Takeaways (4 pts) — binary
        self.scores['b4_takeaways'] = 4 if notes_check['b4_takeaways']['status'] == 'Yes' else 0

        # B4: Questions (3 pts)
        self.scores['b4_questions'] = 3 if notes_check['b4_questions']['status'] == 'Yes' else (1 if notes_check['b4_questions']['status'] == 'Partial' else 0)

        # B4: Timing accuracy (3 pts) — binary
        self.scores['b4_timing_accuracy'] = 3 if notes_check['b4_timing_accuracy']['status'] == 'Yes' else 0

        # C: Notes & Documentation (20 pts, 6 binary items)
        self.scores['c_template_named'] = 3 if notes_check['c_template_named']['status'] == 'Yes' else 0
        self.scores['c_overview_tab'] = 3 if notes_check['c_overview_tab']['status'] == 'Yes' else 0
        self.scores['c_session_notes_detailed'] = 5 if notes_check['c_session_notes_detailed']['status'] == 'Yes' else 0
        self.scores['c_exam_progress'] = 3 if notes_check['c_exam_progress']['status'] == 'Yes' else 0
        self.scores['c_next_steps_written'] = 3 if notes_check['c_next_steps_written']['status'] == 'Yes' else 0
        self.scores['c_activity_tracking'] = 3 if notes_check['c_activity_tracking']['status'] == 'Yes' else 0

        # D: Professionalism (15 pts, 5 binary items)
        self.scores['d_demeanor'] = 3 if notes_check['d_demeanor']['status'] == 'Yes' else 0
        self.scores['d_no_guarantees'] = 3 if notes_check['d_no_guarantees']['status'] == 'Yes' else 0
        self.scores['d_proper_channels'] = 3 if notes_check['d_proper_channels']['status'] == 'Yes' else 0
        self.scores['d_on_time'] = 3 if notes_check['d_on_time']['status'] == 'Yes' else 0
        self.scores['d_approved_platforms'] = 3 if notes_check['d_approved_platforms']['status'] == 'Yes' else 0

        # --- Compute category totals ---
        a_total = (self.scores['a1_structure'] + self.scores['a2_schedule'] +
                   self.scores['a2_fl_exams'] + self.scores['a2_aamc'] +
                   self.scores['a3_presession'] + self.scores['a3_survey'] +
                   self.scores['a3_postsession_notes'] + self.scores['a3_shared'] +
                   self.scores['a4_specific'])
        b_total = (self.scores['b1_probing'] + self.scores['b1_student_talks'] +
                   self.scores['b1_no_remap'] + self.scores['b2_identifies_reasons'] +
                   self.scores['b2_no_excuses'] + self.scores['b2_actionable'] +
                   self.scores['b3_three_qs'] + self.scores['b3_student_teaches'] +
                   self.scores['b3_paragraph_feedback'] + self.scores['b4_takeaways'] +
                   self.scores['b4_questions'] + self.scores['b4_timing_accuracy'])
        c_total = (self.scores['c_template_named'] + self.scores['c_overview_tab'] +
                   self.scores['c_session_notes_detailed'] + self.scores['c_exam_progress'] +
                   self.scores['c_next_steps_written'] + self.scores['c_activity_tracking'])
        d_total = (self.scores['d_demeanor'] + self.scores['d_no_guarantees'] +
                   self.scores['d_proper_channels'] + self.scores['d_on_time'] +
                   self.scores['d_approved_platforms'])

        raw_total = a_total + b_total + c_total + d_total

        # Determine rating using new scale
        if raw_total >= 120:
            rating = 'Excellent'
        elif raw_total >= 100:
            rating = 'Satisfactory'
        elif raw_total >= 80:
            rating = 'Needs Improvement'
        else:
            rating = 'Unsatisfactory'

        # Build justifications per category
        self.justifications['A'] = self._build_category_justification('A', notes_check)
        self.justifications['B'] = self._build_category_justification('B', notes_check)
        self.justifications['C'] = self._build_category_justification('C', notes_check)
        self.justifications['D'] = self._build_category_justification('D', notes_check)

        # Build missing items per category
        self.missing_items['A'] = [k for k in notes_check if k.startswith('a') and notes_check[k]['status'] == 'No']
        self.missing_items['B'] = [k for k in notes_check if k.startswith('b') and notes_check[k]['status'] == 'No']
        self.missing_items['C'] = [k for k in notes_check if k.startswith('c') and notes_check[k]['status'] == 'No']
        self.missing_items['D'] = [k for k in notes_check if k.startswith('d') and notes_check[k]['status'] == 'No']

        self.findings = {
            'info': info,
            'notes_check': notes_check,
            'scores': self.scores,
            'a_total': a_total,
            'b_total': b_total,
            'c_total': c_total,
            'd_total': d_total,
            'raw_total': raw_total,
            'rating': rating
        }
        return self.findings

    def _build_category_justification(self, category_prefix, notes_check):
        """Build a justification string for a category from check results."""
        prefix = category_prefix.lower()
        parts = []
        for key, check in notes_check.items():
            if key.startswith(prefix) and key.count('_') >= 1:
                label = key.replace('_', ' ').upper()
                if check['status'] == 'Yes':
                    parts.append('{}: Pass'.format(label))
                elif check['status'] == 'Partial':
                    parts.append('{}: Partial — {}'.format(label, check['evidence']))
                else:
                    parts.append('{}: Missing — {}'.format(label, check['evidence']))
        return '; '.join(parts) if parts else 'No items evaluated.'

    def _get_biggest_risk(self):
        """Determine biggest risk based on category totals."""
        f = self.findings
        if f['a_total'] < 25:
            return "SOP compliance is critically low — session structure, scheduling, and documentation requirements were largely unmet."
        elif f['c_total'] < 10:
            return "Notes and documentation are severely lacking — student has no take-home reference material."
        elif f['b_total'] < 25:
            return "Coaching quality needs significant improvement — Socratic method, weakness identification, or passage practice were deficient."
        elif f['d_total'] < 10:
            return "Professionalism concerns detected — review communication channels and demeanor."
        else:
            return "Minor gaps in documentation or coaching may impact student's ability to follow study plan independently."

    def _get_top_fixes(self):
        """Generate top 3 fixes based on lowest-scoring areas."""
        fixes = []
        f = self.findings
        if f['a_total'] < 30:
            fixes.append("Ensure full SOP compliance: confirm session structure, create study schedule with FL exam dates, and complete all pre/post-session tasks")
        if self.scores.get('a2_fl_exams', 0) == 0:
            fixes.append("Document the FL exam schedule explicitly (10 FLs: JW FL 1-6 + AAMC exams, with specific dates for each)")
        if self.scores.get('a2_aamc', 0) == 0:
            fixes.append("Schedule AAMC question packs/resources (if student has them) with deadlines")
        if f['c_total'] < 12:
            fixes.append("Create proper session notes using the Notes v2 template with overview, detailed notes, exam progress, and next steps")
        if f['b_total'] < 30:
            fixes.append("Improve coaching quality: use more Socratic questioning, have student teach back concepts, and provide detailed passage feedback")
        if self.scores.get('a3_shared', 0) == 0:
            fixes.append("Share session documentation with student and director emails")
        if f['d_total'] < 12:
            fixes.append("Review professionalism standards: use approved platforms, maintain proper demeanor, avoid score guarantees")
        return fixes[:3]

    def _generate_tutor_feedback(self):
        """Generate detailed tutor feedback."""
        info = self.findings['info']
        f = self.findings

        positives = []
        if f['b_total'] >= 35:
            positives.append(("Strong Coaching Quality", "Socratic method, weakness identification, and student engagement were well-executed. Score: {}/50.".format(f['b_total'])))
        if f['d_total'] >= 12:
            positives.append(("Professional Conduct", "Professionalism standards were met consistently. Score: {}/15.".format(f['d_total'])))
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
        if f['a_total'] < 25:
            improvements.append({
                'title': 'Critical: SOP Compliance Deficient',
                'what': 'Multiple SOP requirements were not met including session structure, scheduling, and pre/post-session tasks.',
                'why': 'SOP compliance ensures consistent quality and that students receive all required planning and documentation.',
                'fix': 'Review the SOP checklist before each session. Use a pre-session checklist to ensure all items are covered. Budget time at end for documentation.'
            })

        if f['c_total'] < 10:
            improvements.append({
                'title': 'Critical: Inadequate Session Documentation',
                'what': 'The session produced minimal documented notes. Key sections are missing from the notes document.',
                'why': 'Student has no reference document for their study plan, exam schedule, or strategies discussed. They cannot follow a structured plan independently.',
                'fix': 'Create a Google Doc immediately using the Notes v2 template. Include: Student Snapshot, Exam Schedule, Session Notes, Next Steps. Share with student AND directors. Budget 10-15 minutes at session end for documentation.'
            })

        if f['b_total'] < 30:
            improvements.append({
                'title': 'Improve: Coaching Methodology',
                'what': 'Coaching quality indicators suggest room for improvement in Socratic method usage, weakness identification, or passage practice.',
                'why': 'Effective coaching drives better student outcomes. Students learn more when they explain concepts back and identify their own weaknesses.',
                'fix': 'Ask more open-ended questions. Have the student teach back concepts. When reviewing passages, ask 3+ questions and have the student explain their reasoning.'
            })

        if self.scores.get('a2_fl_exams', 0) < 4:
            improvements.append({
                'title': 'Missing: FL Exam Schedule with Dates',
                'what': 'FL sequencing may have been discussed verbally but specific dates were not documented.',
                'why': 'Student needs clarity on which test to take each week. Without a documented schedule, they may sequence incorrectly.',
                'fix': 'Create a table: Week | Date | Exam | Notes. Be explicit about when to start AAMC materials.'
            })

        if self.missing_items.get('A') and len(self.missing_items['A']) > 2:
            improvements.append({
                'title': 'Missing: Session-Specific Requirements',
                'what': 'Several session-specific items were not addressed (baseline, test date, weak areas, commitments, or next session plan).',
                'why': 'These items form the foundation of a personalized study plan. Without them, recommendations may be generic.',
                'fix': 'Use a Session 1 checklist to confirm: test date, baseline score, target score, constraints, weak areas, and next session date.'
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
        """Generate the full comprehensive grading report using 4-category 135-point rubric."""
        if not self.findings:
            self.grade()
        if self.course_type == 'cars':
            return self._generate_cars_report()

        f = self.findings
        info = f['info']
        notes_check = f['notes_check']

        positives, improvements = self._generate_tutor_feedback()
        gap_items = self._generate_gap_analysis()
        notes_v2 = self._generate_notes_v2_clean()

        sep = "________________________________________________________________________________"

        # Score label helper
        def _score_line(key, label, max_pts):
            pts = self.scores.get(key, 0)
            status = notes_check.get(key, {}).get('status', '?')
            evidence = notes_check.get(key, {}).get('evidence', '')
            return "{:<45} | {:>3}/{:<3} | {:<8} | {}".format(label, pts, max_pts, status, evidence[:60])

        report = """SESSION 1 GRADING REPORT (135-Point Rubric)

Student: {student}
Tutor: {tutor}
Session Date: {date}
Test Date: {test_date}
Graded By: JW Session Notes Grader (Agent)

{sep}

SECTION 1: QUICK VERDICT

Overall Rating: {rating}
Raw Score: {raw_total}/135
Biggest Risk: {risk}

Top 3 Fixes

""".format(
            student=self.student_name,
            tutor=self.tutor_name,
            date=self.session_date,
            test_date=info['test_date'],
            rating=f['rating'].upper(),
            raw_total=f['raw_total'],
            risk=self._get_biggest_risk(),
            sep=sep
        )

        for i, fix in enumerate(self._get_top_fixes(), 1):
            report += "{}. {}\n".format(i, fix)

        report += """
{sep}

SECTION 2: CATEGORY SCORES

================================================================================
A. SOP COMPLIANCE ({a_total}/50)
================================================================================

A1. Session Structure & Timing (10 pts)
{a1_line}

A2. Study Schedule & Exam Planning (14 pts)
{a2_schedule_line}
{a2_fl_line}
{a2_aamc_line}

A3. Pre/Post-Session Tasks (12 pts)
{a3_presession_line}
{a3_survey_line}
{a3_postsession_line}
{a3_shared_line}

A4. Session-Specific Requirements (14 pts)
{a4_line}

""".format(
            a_total=f['a_total'],
            a1_line=_score_line('a1_structure', 'Session structure & agenda', 10),
            a2_schedule_line=_score_line('a2_schedule', 'Study schedule created', 4),
            a2_fl_line=_score_line('a2_fl_exams', 'FL exam schedule with dates', 6),
            a2_aamc_line=_score_line('a2_aamc', 'AAMC question packs scheduled', 4),
            a3_presession_line=_score_line('a3_presession', 'Pre-session preparation', 3),
            a3_survey_line=_score_line('a3_survey', 'Survey/intake form', 3),
            a3_postsession_line=_score_line('a3_postsession_notes', 'Post-session notes created', 3),
            a3_shared_line=_score_line('a3_shared', 'Document shared with student', 3),
            a4_line=_score_line('a4_specific', 'Session-specific requirements', 14),
            sep=sep
        )

        report += """================================================================================
B. COACHING QUALITY ({b_total}/50)
================================================================================

B1. Socratic Method (15 pts)
{b1_probing_line}
{b1_student_line}
{b1_remap_line}

B2. Weakness Identification (15 pts)
{b2_reasons_line}
{b2_excuses_line}
{b2_actionable_line}

B3. Passage Practice (10 pts)
{b3_qs_line}
{b3_teaches_line}
{b3_feedback_line}

B4. Student Engagement (10 pts)
{b4_takeaways_line}
{b4_questions_line}
{b4_timing_line}

""".format(
            b_total=f['b_total'],
            b1_probing_line=_score_line('b1_probing', 'Probing questions used', 5),
            b1_student_line=_score_line('b1_student_talks', 'Student does the talking', 5),
            b1_remap_line=_score_line('b1_no_remap', 'No direct answer-giving', 5),
            b2_reasons_line=_score_line('b2_identifies_reasons', 'Identifies root causes', 5),
            b2_excuses_line=_score_line('b2_no_excuses', 'No excuse-making language', 5),
            b2_actionable_line=_score_line('b2_actionable', 'Actionable recommendations', 5),
            b3_qs_line=_score_line('b3_three_qs', '3+ passage questions', 4),
            b3_teaches_line=_score_line('b3_student_teaches', 'Student teaches back', 3),
            b3_feedback_line=_score_line('b3_paragraph_feedback', 'Paragraph-level feedback', 3),
            b4_takeaways_line=_score_line('b4_takeaways', 'Takeaways summarized', 4),
            b4_questions_line=_score_line('b4_questions', 'Checks for questions', 3),
            b4_timing_line=_score_line('b4_timing_accuracy', 'Timing/punctuality', 3)
        )

        report += """================================================================================
C. NOTES & DOCUMENTATION ({c_total}/20)
================================================================================

{c_template_line}
{c_overview_line}
{c_detailed_line}
{c_exam_line}
{c_next_line}
{c_activity_line}

""".format(
            c_total=f['c_total'],
            c_template_line=_score_line('c_template_named', 'Notes template used', 3),
            c_overview_line=_score_line('c_overview_tab', 'Overview/snapshot section', 3),
            c_detailed_line=_score_line('c_session_notes_detailed', 'Detailed session notes', 5),
            c_exam_line=_score_line('c_exam_progress', 'Exam progress tracking', 3),
            c_next_line=_score_line('c_next_steps_written', 'Next steps documented', 3),
            c_activity_line=_score_line('c_activity_tracking', 'Activity tracking', 3)
        )

        report += """================================================================================
D. PROFESSIONALISM ({d_total}/15)
================================================================================

{d_demeanor_line}
{d_guarantees_line}
{d_channels_line}
{d_ontime_line}
{d_platforms_line}

""".format(
            d_total=f['d_total'],
            d_demeanor_line=_score_line('d_demeanor', 'Professional demeanor', 3),
            d_guarantees_line=_score_line('d_no_guarantees', 'No score guarantees', 3),
            d_channels_line=_score_line('d_proper_channels', 'Proper comm channels', 3),
            d_ontime_line=_score_line('d_on_time', 'On time', 3),
            d_platforms_line=_score_line('d_approved_platforms', 'Approved platforms only', 3)
        )

        report += """{sep}

SECTION 3: TRANSCRIPT VS. NOTES GAP ANALYSIS

What Was Discussed in Transcript (Should Have Been in Notes)

Topic Discussed                                           | In Notes?
----------------------------------------------------------|----------
""".format(sep=sep)

        for topic, discussed, in_notes in gap_items:
            if discussed:
                report += "{:57} | {}\n".format(topic[:57], in_notes)

        report += """
{sep}

SECTION 4: RECOMMENDED NOTES REWRITE (NOTES V2)

Given that multiple critical SOP items are missing from notes, below is a recommended rewrite.

{sep}

{notes_v2}

{sep}

SECTION 5: TUTOR FEEDBACK

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
A. SOP Compliance                       | {a_total}/50
B. Coaching Quality                     | {b_total}/50
C. Notes & Documentation                | {c_total}/20
D. Professionalism                      | {d_total}/15
----------------------------------------|-------
RAW TOTAL                               | {raw_total}/135

{sep}

OVERALL ASSESSMENT: {rating}

Grade Scale: 120-135 Excellent | 100-119 Satisfactory | 80-99 Needs Improvement | Below 80 Unsatisfactory

Summary:
{summary}

Recommended Actions:
1. Tutor should immediately create and share a comprehensive Session 1 Google Doc (see Notes v2 above)
2. Confirm next session date in writing
3. Future sessions should include 5-10 minutes at end for documentation review with student

{sep}

Graded by: JW Session Notes Grader Agent
Grading Agent Version: 2.0
Rubric: 4-Category 135-Point System (SOP Compliance, Coaching Quality, Notes & Documentation, Professionalism)
Reference Documents: first_session_sop_agent.md, grading_first_session_agent.md
""".format(
            tutor=self.tutor_name.split()[0] if self.tutor_name else 'Tutor',
            a_total=f['a_total'],
            b_total=f['b_total'],
            c_total=f['c_total'],
            d_total=f['d_total'],
            raw_total=f['raw_total'],
            rating=f['rating'].upper(),
            summary=self._generate_summary(),
            sep=sep
        )

        return report

    def _generate_summary(self):
        """Generate overall summary based on new 135-point scale."""
        raw = self.findings['raw_total']
        if raw >= 120:
            return "Excellent session with comprehensive documentation and strong coaching. All major SOP items are addressed and the student has clear direction."
        elif raw >= 100:
            return "Satisfactory session. Most SOP requirements met with adequate coaching quality. Minor improvements recommended for completeness."
        elif raw >= 80:
            return "The session needs improvement. While some elements were addressed, significant gaps exist in SOP compliance, coaching methodology, or documentation. The student may lack sufficient take-home artifacts to follow a structured study plan independently."
        else:
            return "Unsatisfactory session with significant gaps across multiple categories. Immediate follow-up is required to ensure the student has necessary study materials, clear direction, and proper documentation. Priority action: address SOP compliance and create comprehensive session notes immediately."

    def _grade_cars(self):
        """Grade using the CARS Strategy Course 125-point rubric."""
        text = (self.transcript or '').lower()
        notes = (self.student_notes or '').lower()
        combined = text + ' ' + notes

        # ── A. SOP Compliance (45 pts) ──
        # A1. Session Structure & Timing (10 pts)
        a1 = 0
        if re.search(r'(?:intro|welcome|how are you|good to see)', text) and re.search(r'(?:wrap.?up|takeaway|closing|next steps)', text):
            a1 += 4
        elif re.search(r'(?:intro|welcome|how are you)', text) or re.search(r'(?:wrap.?up|takeaway|closing)', text):
            a1 += 2
        agenda_signals = sum(1 for p in [r'video', r'strateg', r'passage', r'mapping', r'question'] if re.search(p, text))
        if agenda_signals >= 3:
            a1 += 4
        elif agenda_signals >= 1:
            a1 += 2
        if re.search(r'(?:takeaway|progression|next steps|questions?\s*(?:for me|before we))', text):
            a1 += 2

        # A2. Study Schedule & Exam Planning (12 pts)
        a2 = 0
        if self.sop_study_schedule == 'yes' or re.search(r'(?:study schedule|google sheet|spreadsheet)', combined):
            a2 += 4
        elif self.sop_study_schedule == 'partial':
            a2 += 2
        total_dates, march5_count = self._count_march5_exams(combined)
        fl_refs = re.findall(r'(?:full.?length|FL|practice\s*exam)', combined, re.I)
        if self.sop_full_length_exams == 'yes':
            a2 += 5
        elif self.sop_full_length_exams == 'partial':
            a2 += 3
        elif len(fl_refs) >= 6 and (march5_count == 0 or march5_count < total_dates * 0.3):
            a2 += 5
        elif len(fl_refs) >= 4 and march5_count < total_dates * 0.7:
            a2 += 3
        if re.search(r'(?:test\s*(?:date|day)|mcat\s*(?:is|on|date))', combined):
            a2 += 3

        # A3. Pre-Session & Post-Session Tasks (12 pts)
        a3 = 0
        if re.search(r'pre.?session\s*notes?', combined) or re.search(r'(?:before\s*(?:the|our)\s*session|prepared|reviewed.*before)', combined):
            a3 += 3
        if re.search(r'(?:survey|diagnostic|baseline|passage\s*(?:breakdown|video))', combined):
            a3 += 3
        if re.search(r'(?:in.?session\s*notes?|session\s*notes?\s*completed?)', combined):
            a3 += 3
        elif notes.strip():
            a3 += 3
        if re.search(r'(?:shared?\s*with|molly|carl|anastasia)', combined):
            a3 += 3

        # A4. Session-Specific Requirements (11 pts)
        a4 = 0
        if self.session_number == '1':
            if re.search(r'(?:calendly|booking|schedule.*next|link.*next)', combined):
                a4 += 3
            video_keywords = ['reading for arguments', 'reading for support', 'analogy', 'assumption',
                              'subtle weakener', 'mapping tips', 'strategy video']
            video_matches = sum(1 for v in video_keywords if v in combined)
            if video_matches >= 2:
                a4 += 3
            elif video_matches >= 1:
                a4 += 1
            a4 += 5
        else:
            if re.search(r'(?:hw\s*tracker|homework\s*tracker|timed\s*cars|cars\s*assignment)', combined):
                a4 += 3
            if re.search(r'(?:troubleshoot|test.?day|running\s*out\s*of\s*time|toolkit)', combined):
                a4 += 2
            a4 += 6

        sop_total = a1 + a2 + a3 + a4

        # ── B. Coaching Quality (45 pts) ──
        # B1. Socratic Method & Guided Questioning (15 pts)
        b1 = 0
        probing_patterns = [r'what do you think', r'why (?:is|do|would)', r'how would you',
                            r'can you explain', r'walk me through', r'tell me',
                            r'in your own words', r'what happens']
        probing_count = sum(len(re.findall(p, text)) for p in probing_patterns)
        if probing_count >= 5:
            b1 += 5
        elif probing_count >= 2:
            b1 += 3
        b1 += 5
        if not re.search(r'(?:let me (?:map|do) (?:it|this) for you|i\'ll map)', text):
            b1 += 5

        # B2. CARS-Specific Coaching (15 pts)
        b2 = 0
        error_types = ['paragraph map', 'main idea', 'misread', 'overconfident', 'overthink']
        error_count = sum(1 for e in error_types if e in text)
        if error_count >= 2:
            b2 += 5
        elif error_count >= 1:
            b2 += 3
        excuse_patterns = [r'just guess', r'silly mistake', r'not good at cars', r'i suck at']
        has_excuses = any(re.search(p, text) for p in excuse_patterns)
        followup_patterns = [r'let\'s look at', r'walk me through', r'what made you', r'why did you']
        has_followup = any(re.search(p, text) for p in followup_patterns)
        if has_excuses and has_followup:
            b2 += 5
        elif not has_excuses:
            b2 += 5
        if re.search(r'(?:why we|reason.*map|purpose.*map|jw.*approach|jack westin.*method|because.*map)', text):
            b2 += 5
        elif re.search(r'(?:map|mapping|paragraph\s*map)', text):
            b2 += 3

        # B3. Passage Practice Execution (8 pts)
        b3 = 0
        question_refs = re.findall(r'question\s*(?:\d|#|number)', text)
        if len(question_refs) >= 3 or re.search(r'(?:three|3)\s*(?:or more\s*)?questions?', text):
            b3 += 3
        elif question_refs or re.search(r'question', text):
            b3 += 1
        if re.search(r'(?:read\s*(?:it\s*)?aloud|read\s*(?:this|the)\s*(?:sentence|paragraph)|teach.*passage|explain.*passage)', text):
            b3 += 3
        elif re.search(r'(?:read|reading)', text):
            b3 += 1
        if re.search(r'(?:paragraph\s*(?:one|two|three|1|2|3)|per\s*paragraph|each\s*paragraph|feedback.*paragraph)', text):
            b3 += 2

        # B4. Student Engagement & Takeaways (7 pts)
        b4 = 0
        if re.search(r'(?:takeaway|what did you learn|what.*take away|biggest\s*(?:thing|lesson))', text):
            b4 += 3
        if re.search(r'(?:any questions|do you have.*question|before we (?:end|wrap)|anything else)', text):
            b4 += 2
        has_timing = bool(re.search(r'(?:timing|time|minutes|9 passages|90 min|pace|speed)', text))
        has_accuracy = bool(re.search(r'(?:accura|correct|wrong|missed|score|percent)', text))
        if has_timing and has_accuracy:
            b4 += 2
        elif has_timing or has_accuracy:
            b4 += 1

        coaching_total = b1 + b2 + b3 + b4

        # ── C. Notes & Documentation (20 pts) ──
        c = 0
        if re.search(r'(?:course tutoring note|tutoring note.*tutor name)', notes):
            c += 3
        elif notes.strip():
            c += 1
        if re.search(r'(?:overview|survey|diagnostic|baseline)', notes):
            c += 3
        if len(notes) > 500:
            c += 5
        elif len(notes) > 200:
            c += 3
        elif notes.strip():
            c += 1
        if re.search(r'(?:exam\s*progress|fl\s*(?:score|progress|track))', notes):
            c += 3
        if re.search(r'(?:next\s*steps?|action\s*items?|homework|assignment)', notes):
            c += 3
        elif re.search(r'(?:next\s*steps?|action\s*items?)', text):
            c += 1
        if re.search(r'(?:activity\s*completion|column\s*m|col\s*m|tracking\s*spreadsheet)', combined):
            c += 3

        # ── D. Professionalism (15 pts) ──
        d = 0
        if not re.search(r'(?:completely wrong|that\'s wrong|stupid|terrible)', text):
            d += 3
        if not re.search(r'(?:you\'ll (?:definitely|for sure) get|guarantee|promise.*score)', text):
            d += 3
        if not re.search(r'(?:\$\d|price|cost|payment)', text):
            d += 3
        d += 3
        if not re.search(r'(?:my (?:cell|phone|number|instagram|snapchat)|text me at|dm me)', text):
            d += 3

        raw_total = sop_total + coaching_total + c + d

        if raw_total >= 112:
            rating = 'Excellent'
        elif raw_total >= 93:
            rating = 'Satisfactory'
        elif raw_total >= 74:
            rating = 'Needs Improvement'
        else:
            rating = 'Unsatisfactory'

        self.findings = {
            'info': {'session_number': self.session_number},
            'scores': {
                'a1': a1, 'a2': a2, 'a3': a3, 'a4': a4,
                'b1': b1, 'b2': b2, 'b3': b3, 'b4': b4,
                'c': c, 'd': d,
            },
            'sop_total': sop_total,
            'coaching_total': coaching_total,
            'notes_total': c,
            'professionalism_total': d,
            'raw_total': raw_total,
            'max_total': 125,
            'rating': rating,
        }
        return self.findings

    def _generate_cars_report(self):
        """Generate the CARS Strategy Course grading report."""
        f = self.findings
        s = f['scores']
        sep = '________________________________________________________________________________'

        report = """CARS STRATEGY COURSE — SESSION {session} GRADING REPORT

Student: {student}
Tutor: {tutor}
Session Date: {date}
Course: CARS Strategy (Sessions 1-2)
Graded By: JW CARS Session Grader (Agent)

{sep}

QUICK VERDICT

Overall Rating: {rating}
Score: {raw}/{max} ({pct}%)

{sep}

CATEGORY SCORES

A. SOP Compliance — {sop}/45
  A1. Session Structure & Timing: {a1}/10
  A2. Study Schedule & Exam Planning: {a2}/12
  A3. Pre-Session & Post-Session Tasks: {a3}/12
  A4. Session-Specific Requirements (S{session}): {a4}/11

B. Coaching Quality — {coaching}/45
  B1. Socratic Method & Guided Questioning: {b1}/15
  B2. CARS-Specific Coaching: {b2}/15
  B3. Passage Practice Execution: {b3}/8
  B4. Student Engagement & Takeaways: {b4}/7

C. Notes & Documentation — {notes}/20

D. Professionalism — {prof}/15

{sep}

FINAL SCORE SUMMARY

Category                    | Score | Max
----------------------------|-------|-----
A. SOP Compliance           | {sop:3} |  45
B. Coaching Quality         | {coaching:3} |  45
C. Notes & Documentation    | {notes:3} |  20
D. Professionalism          | {prof:3} |  15
----------------------------|-------|-----
TOTAL                       | {raw:3} | 125

Overall Rating: {rating}

Grade Scale: 112-125 Excellent | 93-111 Satisfactory | 74-92 Needs Improvement | <74 Unsatisfactory

{sep}

Graded by: JW CARS Session Grader Agent
""".format(
            session=self.session_number,
            student=self.student_name,
            tutor=self.tutor_name,
            date=self.session_date,
            rating=f['rating'],
            raw=f['raw_total'],
            max=f['max_total'],
            pct=round(f['raw_total'] / 125 * 100),
            sop=f['sop_total'],
            coaching=f['coaching_total'],
            notes=f['notes_total'],
            prof=f['professionalism_total'],
            a1=s['a1'], a2=s['a2'], a3=s['a3'], a4=s['a4'],
            b1=s['b1'], b2=s['b2'], b3=s['b3'], b4=s['b4'],
            sep=sep,
        )
        return report


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
                course_type=data.get('course_type', '515'),
                session_number=data.get('session_number', '1'),
            )

            findings = grader.grade()
            report = grader.generate_report()

            # Send grading report to all four directors
            subject = 'Session Grading Report - {} (Tutor: {})'.format(
                data['student_name'], data['tutor_name'])
            email_sent = send_email(DIRECTOR_EMAILS, subject, report)

            response_data = {
                'success': True,
                'scores': findings['scores'],
                'overall_rating': findings['rating'],
                'email_sent': email_sent,
                'report': report,
            }
            if grader.course_type == 'cars':
                response_data['raw_total'] = findings['raw_total']
                response_data['max_total'] = findings['max_total']
            else:
                response_data['average_score'] = findings.get('average', findings.get('raw_total'))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

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
