# -*- coding: utf-8 -*-
"""
JW Session 1 Grading App
Accepts transcript uploads, grades sessions, and emails results.
Full comprehensive grading with detailed feedback.
Supports Fathom.video API integration for automatic transcript retrieval.
"""

import os
import json
import re
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()
app = Flask(__name__)
CORS(app)

# Configuration from environment
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
DIRECTOR_EMAIL = os.getenv('DIRECTOR_EMAIL', 'anastasia@jackwestin.com')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'grader@jackwestin.com')

# Hard-coded director recipients — all grading reports go to these four
DIRECTOR_EMAILS = [
    "anastasia@jackwestin.com",
    "carlb@jackwestin.com",
    "Molly@jackwestin.com",
    "adamrs@jackwestin.com",
]
FATHOM_API_KEY = os.getenv('FATHOM_API_KEY', '')


class FathomClient:
    """Client for interacting with Fathom.video API to retrieve recordings and transcripts."""
    
    BASE_URL = "https://api.fathom.ai/external/v1"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or FATHOM_API_KEY
        
    def _make_request(self, endpoint, method='GET'):
        """Make an authenticated request to the Fathom API."""
        if not self.api_key:
            return {'error': 'Fathom API key not configured', 'success': False}
        
        url = "{}{}".format(self.BASE_URL, endpoint)
        headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            # Create SSL context for HTTPS requests
            ssl_context = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))
                return {'success': True, 'data': data}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            return {'success': False, 'error': 'Fathom API error {}: {}'.format(e.code, error_body)}
        except urllib.error.URLError as e:
            # Try again without SSL verification if certificate issue
            if 'CERTIFICATE_VERIFY_FAILED' in str(e.reason):
                try:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        return {'success': True, 'data': data}
                except Exception as retry_e:
                    return {'success': False, 'error': 'SSL retry failed: {}'.format(str(retry_e))}
            return {'success': False, 'error': 'Network error: {}'.format(str(e.reason))}
        except json.JSONDecodeError as e:
            return {'success': False, 'error': 'Invalid JSON response from Fathom'}
        except Exception as e:
            return {'success': False, 'error': 'Unexpected error: {}'.format(str(e))}
    
    def get_recordings(self, limit=50):
        """Fetch recent meetings/recordings from Fathom."""
        result = self._make_request('/meetings?limit={}'.format(limit))
        
        if not result.get('success'):
            return result
        
        recordings = []
        data = result.get('data', {})
        
        # Handle different response structures
        meetings = data.get('meetings', [])
        if not meetings and isinstance(data, list):
            meetings = data
        
        for meeting in meetings:
            # Get recording info if available
            recording = meeting.get('recording', {})
            recording_id = recording.get('id', meeting.get('id', ''))
            
            recordings.append({
                'id': recording_id,
                'title': meeting.get('title', 'Untitled Recording'),
                'date': meeting.get('started_at', meeting.get('created_at', ''))[:10] if meeting.get('started_at') or meeting.get('created_at') else '',
                'duration': recording.get('duration', meeting.get('duration', 0)),
                'participants': [p.get('name', p.get('display_name', '')) for p in meeting.get('participants', [])]
            })
        
        return {'success': True, 'recordings': recordings}
    
    def get_transcript(self, recording_id):
        """Retrieve the transcript for a specific recording."""
        if not recording_id:
            return {'success': False, 'error': 'Recording ID is required'}
        
        result = self._make_request('/recordings/{}/transcript'.format(recording_id))
        
        if not result.get('success'):
            return result
        
        transcript_data = result.get('data', {})
        formatted_text = self.format_transcript_text(transcript_data)
        
        # Get recording title for reference
        recording_title = ''
        rec_result = self._make_request('/recordings/{}'.format(recording_id))
        if rec_result.get('success'):
            recording_title = rec_result.get('data', {}).get('title', '')
        
        return {
            'success': True,
            'transcript': formatted_text,
            'recording_title': recording_title,
            'raw_data': transcript_data
        }
    
    def format_transcript_text(self, transcript_data):
        """
        Convert Fathom's transcript JSON format to plain text.
        
        Expected format from Fathom:
        {
          "transcript": [
            {
              "speaker": {"display_name": "John Smith"},
              "text": "Let's revisit the budget allocations.",
              "timestamp": "00:05:32"
            }
          ]
        }
        
        Output format:
        [00:05:32] John Smith: Let's revisit the budget allocations.
        """
        if not transcript_data:
            return ''
        
        lines = []
        
        # Get the transcript array - handle multiple possible structures
        segments = []
        if isinstance(transcript_data, dict):
            segments = transcript_data.get('transcript', [])
            if not segments:
                segments = transcript_data.get('segments', [])
            if not segments:
                segments = transcript_data.get('utterances', [])
        elif isinstance(transcript_data, list):
            segments = transcript_data
        
        for segment in segments:
            # Extract speaker name - handle nested structure
            speaker = 'Unknown'
            speaker_data = segment.get('speaker', {})
            if isinstance(speaker_data, dict):
                speaker = speaker_data.get('display_name', speaker_data.get('name', 'Unknown'))
            elif isinstance(speaker_data, str):
                speaker = speaker_data
            
            # Extract text content
            text = segment.get('text', segment.get('content', ''))
            
            # Extract timestamp
            timestamp = segment.get('timestamp', '')
            
            if text:
                if timestamp:
                    # Format: [HH:MM:SS] Speaker Name: Spoken text
                    lines.append("[{}] {}: {}".format(timestamp, speaker, text.strip()))
                else:
                    # Fallback without timestamp
                    lines.append("{}: {}".format(speaker, text.strip()))
        
        # If no segments found, check for plain text format
        if not lines and isinstance(transcript_data, dict):
            if 'text' in transcript_data:
                return transcript_data['text']
            if 'content' in transcript_data:
                return transcript_data['content']
        
        return '\n\n'.join(lines)
    
    def is_configured(self):
        """Check if Fathom API is configured."""
        return bool(self.api_key)


class SessionGrader:
    """Comprehensive grading engine for Session 1 tutoring transcripts."""

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
        self.scores = {}
        self.justifications = {}
        self.missing_items = {}
        self.findings = {}
        
    def extract_info(self):
        """Extract key information from transcript."""
        # Test date patterns
        test_date_match = re.search(r'(?:April|May|June|July|August|September)\s+\d{1,2}(?:th|st|nd|rd)?(?:,?\s*\d{4})?', self.transcript, re.I)
        test_date = test_date_match.group(0) if test_date_match else 'Not found'
        
        # Baseline score
        baseline_match = re.search(r'(\d{3})\s*(?:on|diagnostic|baseline|starting|unscored)', self.transcript, re.I)
        if not baseline_match:
            baseline_match = re.search(r'(?:got|scored|have)\s*(?:a|an)?\s*(\d{3})', self.transcript, re.I)
        baseline = baseline_match.group(1) if baseline_match else 'Not found'
        
        # Target score
        target_match = re.search(r'(?:need|want|goal|target|get)\s*(?:a|an)?\s*(\d{3})', self.transcript, re.I)
        target = target_match.group(1) if target_match else 'Not found'
        
        # Student constraints
        has_classes = bool(re.search(r'(?:class|classes|semester|school|course)', self.transcript, re.I))
        has_work = bool(re.search(r'(?:work|job|full.?time)', self.transcript, re.I))
        has_adhd = bool(re.search(r'ADHD|accommodation|stop.?the.?clock', self.transcript, re.I))
        
        # Weak areas mentioned
        weak_chem = bool(re.search(r'(?:chem|chemistry|physics|orgo|organic)', self.transcript, re.I))
        weak_bio = bool(re.search(r'(?:bio|biochem|biology)', self.transcript, re.I))
        
        # Strong areas
        strong_cars = bool(re.search(r'(?:CARS|reading|good at CARS|strong.*CARS)', self.transcript, re.I))
        strong_psych = bool(re.search(r'(?:psych|soc|psychology|sociology)', self.transcript, re.I))
        
        # Session elements
        has_fl_discussion = bool(re.search(r'(?:full.?length|FL|practice\s*(?:exam|test))', self.transcript, re.I))
        has_aamc = bool(re.search(r'AAMC', self.transcript, re.I))
        has_aamc_qpacks = bool(re.search(r'(?:question\s*pack|q[\-\s]*pack|section\s*bank|flashcard|official\s*prep|diagnostic\s*tool)', self.transcript, re.I))
        has_strategy = bool(re.search(r'(?:strategy|approach|technique|method|how to)', self.transcript, re.I))
        has_next_session = bool(re.search(r'(?:next\s+session|see\s+you|follow.?up|two\s+or\s+three\s+weeks)', self.transcript, re.I))
        
        # Action items in notes
        action_items = re.findall(r'ACTION\s*ITEM[:\s]+([^\n]+)', self.transcript, re.I)
        
        # Topics discussed
        topics_discussed = []
        if re.search(r'(?:acid|base|pH|pKa|Henderson)', self.transcript, re.I):
            topics_discussed.append('Acid-base/pH')
        if re.search(r'(?:Ksp|equilibrium|Le\s*Chatelier)', self.transcript, re.I):
            topics_discussed.append('Equilibrium/Ksp')
        if re.search(r'(?:physics|velocity|distance|unit|kinematics)', self.transcript, re.I):
            topics_discussed.append('Physics/Units')
        if re.search(r'(?:Michaelis|Menten|enzyme|Kcat)', self.transcript, re.I):
            topics_discussed.append('Enzyme kinetics')
        if re.search(r'(?:action\s*potential|neuron|sodium|potassium)', self.transcript, re.I):
            topics_discussed.append('Action potentials')
        if re.search(r'(?:amino\s*acid|protein|protonated)', self.transcript, re.I):
            topics_discussed.append('Amino acids')
        if re.search(r'(?:passage|experimental|discrete)', self.transcript, re.I):
            topics_discussed.append('Passage strategy')
            
        info = {
            'test_date': test_date,
            'baseline_score': baseline,
            'target_score': target,
            'has_classes': has_classes,
            'has_work': has_work,
            'has_adhd': has_adhd,
            'weak_chem': weak_chem,
            'weak_bio': weak_bio,
            'strong_cars': strong_cars,
            'strong_psych': strong_psych,
            'has_fl_discussion': has_fl_discussion,
            'has_aamc': has_aamc,
            'has_aamc_qpacks': has_aamc_qpacks,
            'has_strategy': has_strategy,
            'has_next_session': has_next_session,
            'action_items': action_items,
            'topics_discussed': topics_discussed,
            'transcript_length': len(self.transcript),
        }
        return info
    
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
        # Look for date-like entries near exam references
        date_pattern = r'(?:march\s*5(?:th)?|mar\s*5(?:th)?|3/0?5(?:/\d{2,4})?|03/05(?:/\d{2,4})?)'
        march5_matches = re.findall(date_pattern, text.lower())
        march5_count = len(march5_matches)

        # Count total scheduled dates (any month/day pattern near exam context)
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
        # Look for confirmation patterns in student notes document
        aamc_mentioned = bool(re.search(r'aamc', notes_lower))
        if not aamc_mentioned:
            return False
        # Check for positive confirmation signals
        confirmation_patterns = [
            r'aamc.*(?:assign|scheduled|complete|yes|done|plan|sequenc|deadline)',
            r'(?:assign|scheduled|complete|yes|done|plan|sequenc|deadline).*aamc',
            r'(?:all|every)\s+aamc',
            r'aamc\s+(?:fl|full.?length|section\s*bank|q.?pack)',
        ]
        return any(re.search(p, notes_lower) for p in confirmation_patterns)

    def check_notes_present(self):
        """Check which SOP items are present in documented notes/action items.

        Aligned with the 4-category 135-point rubric (A/B/C/D).
        """
        action_text = '\n'.join(re.findall(r'ACTION\s*ITEM[:\s]+([^\n]+)', self.transcript, re.I))

        # Detect if student has no AAMC question packs
        combined_text = (action_text + ' ' + self.transcript).lower()
        has_no_aamc_qp = bool(re.search(r'(?:no\s+aamc|doesn.t\s+have\s+aamc|does\s+not\s+have\s+aamc|don.t\s+have\s+aamc)', combined_text))

        # AAMC question pack keywords (separate from exams)
        qpack_pattern = r'(?:question\s*pack|q[\-\s]*pack|section\s*bank|flashcard|official\s*prep|diagnostic\s*tool)'
        has_qpack_ref = bool(re.search(qpack_pattern, combined_text))

        # Check for March 5th placeholder dates in exam schedule
        combined_for_dates = action_text + ' ' + self.student_notes
        total_dates, march5_count = self._count_march5_exams(combined_for_dates)
        has_fl_ref = bool(re.search(r'FL|full.?length|Feb\s*\d|JW\s*FL|Jack\s*Westin\s*FL|practice\s*exam', action_text, re.I))

        # Determine FL exam schedule status accounting for March 5th placeholder
        if has_fl_ref:
            if march5_count > 0 and total_dates > 0 and march5_count >= total_dates * 0.7:
                fl_status = 'No'
                fl_evidence = 'Exam dates use default March 5th placeholder — not actually scheduled by tutor'
            elif march5_count > 0 and total_dates > march5_count:
                fl_status = 'Partial'
                fl_evidence = 'Some exams scheduled but {} of {} dates are the March 5th default placeholder'.format(march5_count, total_dates)
            else:
                fl_status = 'Partial'
                fl_evidence = self._get_evidence(action_text, r'(?:FL|full.?length|practice\s*exam|JW\s*FL)[^.]*') or '(FL exams referenced)'
        else:
            fl_status = 'No'
            fl_evidence = '(Not documented)'

        notes_lower = self.student_notes.lower() if self.student_notes else ''

        checks = {
            # --- A: SOP Compliance helpers ---
            'fl_exam_schedule': {
                'status': fl_status,
                'evidence': fl_evidence
            },
            'aamc_question_packs': {
                'status': 'Yes' if has_no_aamc_qp else ('Partial' if has_qpack_ref or re.search(r'AAMC', action_text, re.I) else 'No'),
                'evidence': 'Student has no AAMC question packs — full credit' if has_no_aamc_qp else (self._get_evidence(action_text, r'(?:question\s*pack|q[\-\s]*pack|section\s*bank|AAMC)[^.]*') or '(Not documented)')
            },
            'below_avg_topics': {
                'status': 'Partial' if re.search(r'(?:review|study|practice|action\s*potential|acid)', action_text, re.I) else 'No',
                'evidence': self._get_evidence(action_text, r'(?:review|study)[^.]*') or '(Not documented)'
            },
            'weekly_checklist': {
                'status': 'No',
                'evidence': '(No weekly checklist in notes)'
            },
            'daily_tasks': {
                'status': 'Partial' if action_text else 'No',
                'evidence': action_text[:100] + '...' if len(action_text) > 100 else action_text or '(No daily tasks documented)'
            },
            'strategy_notes': {
                'status': 'Partial' if re.search(r'(?:practice|discrete|passage)', action_text, re.I) else 'No',
                'evidence': self._get_evidence(action_text, r'(?:practice|discrete|passage)[^.]*') or '(Not documented)'
            },
            'next_session': {
                'status': 'Partial' if re.search(r'(?:session|week|meet)', action_text, re.I) else 'No',
                'evidence': '(Student mentioned timing but no date documented)'
            },
            'baseline_documented': {
                'status': 'No',
                'evidence': '(Discussed verbally but not in notes)'
            },
            'google_doc_shared': {
                'status': 'No',
                'evidence': '(No evidence of shared documentation)'
            },
            'sop_major_takeaways': {
                'status': 'Yes' if self._detect_major_takeaways() else 'No',
                'evidence': 'Tutor asked about major takeaways in last 20% of session.' if self._detect_major_takeaways() else 'Required closing: Tutor must ask "What were your major takeaways?" at session end. This applies to all 515+, Intensive, and CARS sessions.'
            },
            # --- C: Notes & Documentation helpers ---
            'template_named': {
                'status': 'Yes' if re.search(r'(?:session\s*1|session\s*notes|student\s*snapshot)', combined_text) else 'No',
                'evidence': self._get_evidence(combined_text, r'(?:session\s*1|session\s*notes|student\s*snapshot)[^.]*') or '(Template not named)'
            },
            'overview_tab': {
                'status': 'Yes' if re.search(r'(?:overview|snapshot|summary\s*tab)', notes_lower) else 'No',
                'evidence': self._get_evidence(notes_lower, r'(?:overview|snapshot|summary)[^.]*') or '(No overview tab found)'
            },
            'session_notes_detailed': {
                'status': 'Yes' if len(action_text) > 200 else ('Partial' if action_text else 'No'),
                'evidence': 'Detailed session notes present ({} chars)'.format(len(action_text)) if action_text else '(No session notes)'
            },
            'exam_progress': {
                'status': 'Yes' if re.search(r'(?:exam\s*progress|score\s*track|FL\s*\d.*\d{3})', notes_lower + ' ' + combined_text) else 'No',
                'evidence': self._get_evidence(notes_lower, r'(?:exam\s*progress|score\s*track|FL\s*\d[^.]*\d{3})[^.]*') or '(No exam progress tracking)'
            },
            'next_steps_written': {
                'status': 'Yes' if re.search(r'(?:next\s*step|action\s*item|to.?do|homework)', combined_text) else 'No',
                'evidence': self._get_evidence(combined_text, r'(?:next\s*step|action\s*item|to.?do|homework)[^.]*') or '(No next steps documented)'
            },
            'activity_tracking': {
                'status': 'Yes' if re.search(r'(?:daily\s*task|weekly\s*check|activity|tracker)', notes_lower) else 'No',
                'evidence': self._get_evidence(notes_lower, r'(?:daily\s*task|weekly\s*check|activity|tracker)[^.]*') or '(No activity tracking)'
            },
        }
        return checks
    
    def _get_evidence(self, text, pattern):
        match = re.search(pattern, text, re.I)
        return '"' + match.group(0).strip() + '"' if match else None

    def _detect_major_takeaways(self):
        """
        Scan the last 20% of the transcript for the tutor asking about major takeaways.
        Returns True if found, False if not. Must be in the last 20% of the transcript.
        """
        if not self.transcript:
            return False
        cutoff = int(len(self.transcript) * 0.80)
        tail = self.transcript[cutoff:].lower()
        phrases = [
            "what were your major takeaways",
            "what are your takeaways",
            "what's your biggest takeaway",
            "what is your biggest takeaway",
            "what did you take away",
            "what are the main things you're taking away",
            "what would you say your takeaways are",
            "major takeaway",
            "takeaways from today",
            "takeaways from this session",
        ]
        return any(phrase in tail for phrase in phrases)

    def _detect_probing_questions(self):
        """
        Analyze the transcript for tutor probing behavior.
        Returns a dict with signal counts for scoring Category E (Student-Led Learning).
        """
        text = (self.transcript or "").lower()
        positive_patterns = [
            r'what do you think',
            r'why (?:is|do|would|does)',
            r'how would you',
            r'can you explain',
            r'walk me through',
            r'what happens (?:if|when)',
            r"does that make sense",
            r'try it',
            r'you tell me',
            r"what'?s your",
            r'in your own words',
        ]
        positive_count = sum(len(re.findall(p, text)) for p in positive_patterns)
        return {
            'positive_count': positive_count,
            'transcript_length': len(text),
            'probing_density': positive_count / max(len(text) / 1000, 1),
        }

    def grade(self):
        """Run comprehensive grading using 135-point 4-category rubric.

        Categories:
            A. SOP Compliance        — 50 pts
            B. Coaching Quality      — 50 pts
            C. Notes & Documentation — 20 pts
            D. Professionalism       — 15 pts

        Grade scale (raw_total out of 135):
            120-135  Excellent
            100-119  Satisfactory
             80-99   Needs Improvement
             <80     Unsatisfactory
        """
        info = self.extract_info()
        notes_check = self.check_notes_present()
        probing = self._detect_probing_questions()

        # SOP verification inputs act as third source of truth
        # (YES = full credit, PARTIAL = 50%, NO = 0 unless overridden by transcript/notes)

        self.scores = {}
        self.justifications = {}
        self.missing_items = {}

        # =====================================================================
        # A. SOP COMPLIANCE — 50 pts
        # =====================================================================

        # A1: Session Structure & Timing — 10 pts (binary)
        # Did the session follow the expected structure (intro, content, closing)?
        has_intro = bool(re.search(r'(?:how are you|nice to meet|welcome|let.s get started|good to see)', self.transcript, re.I))
        has_closing = info['has_next_session'] or self._detect_major_takeaways()
        has_content = info['has_strategy'] or len(info['topics_discussed']) >= 1
        structure_pts = 0
        if has_intro:
            structure_pts += 3
        if has_content:
            structure_pts += 4
        if has_closing:
            structure_pts += 3
        self.scores['a1_structure'] = min(structure_pts, 10)
        self.justifications['a1_structure'] = "Session structure: intro={}, content={}, closing={}".format(
            'yes' if has_intro else 'no', 'yes' if has_content else 'no', 'yes' if has_closing else 'no')

        # A2: Study Schedule & Exam Planning — 14 pts
        #   a2_schedule: study schedule created (6 pts, binary)
        #   a2_fl_exams: FL exam schedule with dates (4 pts, proportional for March 5 placeholder)
        #   a2_aamc: AAMC materials scheduled (4 pts, binary)
        schedule_ok = (notes_check['weekly_checklist']['status'] != 'No'
                       or notes_check['daily_tasks']['status'] != 'No'
                       or self.sop_study_schedule in ('yes', 'partial'))
        self.scores['a2_schedule'] = 6 if schedule_ok else 0
        self.justifications['a2_schedule'] = "Study schedule present in notes or confirmed via SOP verification." if schedule_ok else "No study schedule found."

        # FL exams — proportional scoring accounting for March 5 placeholder
        fl_status = notes_check['fl_exam_schedule']['status']
        if fl_status == 'Yes' or self.sop_full_length_exams == 'yes':
            self.scores['a2_fl_exams'] = 4
        elif fl_status == 'Partial' or self.sop_full_length_exams == 'partial':
            self.scores['a2_fl_exams'] = 2
        else:
            self.scores['a2_fl_exams'] = 0
        self.justifications['a2_fl_exams'] = notes_check['fl_exam_schedule']['evidence']

        # AAMC materials — binary; dual-source rule applies
        aamc_status = notes_check['aamc_question_packs']['status']
        aamc_notes_confirm = self._check_student_notes_aamc()
        if aamc_status == 'Yes' or self.sop_question_packs == 'yes' or aamc_notes_confirm:
            self.scores['a2_aamc'] = 4
        elif aamc_status == 'Partial' or self.sop_question_packs == 'partial':
            self.scores['a2_aamc'] = 2
        else:
            self.scores['a2_aamc'] = 0
        self.justifications['a2_aamc'] = notes_check['aamc_question_packs']['evidence']

        # A3: Pre/Post-Session Tasks — 12 pts
        #   a3_presession: pre-session preparation (4 pts)
        #   a3_survey: student survey / baseline assessment (4 pts)
        #   a3_postsession_notes: post-session notes written (2 pts)
        #   a3_shared: documentation shared with student/director (2 pts)
        has_presession = info['test_date'] != 'Not found' or info['baseline_score'] != 'Not found'
        self.scores['a3_presession'] = 4 if has_presession else 0
        self.justifications['a3_presession'] = "Pre-session info gathered (test date, baseline)." if has_presession else "No pre-session data found."

        has_survey = info['baseline_score'] != 'Not found' or bool(re.search(r'(?:diagnostic|survey|assessment|unscored)', self.transcript, re.I))
        self.scores['a3_survey'] = 4 if has_survey else 0
        self.justifications['a3_survey'] = "Baseline/diagnostic assessment referenced." if has_survey else "No survey or baseline assessment found."

        has_postsession = notes_check['daily_tasks']['status'] != 'No' or notes_check['strategy_notes']['status'] != 'No'
        self.scores['a3_postsession_notes'] = 2 if has_postsession else 0
        self.justifications['a3_postsession_notes'] = "Post-session notes/action items documented." if has_postsession else "No post-session notes."

        has_shared = notes_check['google_doc_shared']['status'] != 'No'
        self.scores['a3_shared'] = 2 if has_shared else 0
        self.justifications['a3_shared'] = "Documentation shared." if has_shared else "No evidence doc was shared."

        # A4: Session-Specific Requirements — 14 pts
        #   a4_specific covers: below-avg topics (5), next session (3), major takeaways (3), strategy notes (3)
        a4_pts = 0
        if notes_check['below_avg_topics']['status'] == 'Yes':
            a4_pts += 5
        elif notes_check['below_avg_topics']['status'] == 'Partial':
            a4_pts += 3
        if notes_check['next_session']['status'] != 'No':
            a4_pts += 3
        if notes_check['sop_major_takeaways']['status'] == 'Yes':
            a4_pts += 3
        if notes_check['strategy_notes']['status'] != 'No':
            a4_pts += 3
        self.scores['a4_specific'] = min(a4_pts, 14)
        self.justifications['a4_specific'] = "Session-specific items: below-avg topics, next session, takeaways, strategy notes."

        # =====================================================================
        # B. COACHING QUALITY — 50 pts
        # =====================================================================

        # B1: Socratic Method — 15 pts
        #   b1_probing: probing questions used (8 pts)
        #   b1_student_talks: student does the talking (4 pts)
        #   b1_no_remap: tutor does not just re-explain / lecture (3 pts)
        density = probing['probing_density']
        count = probing['positive_count']
        if count >= 8 or density >= 2.0:
            self.scores['b1_probing'] = 8
        elif count >= 5 or density >= 1.2:
            self.scores['b1_probing'] = 6
        elif count >= 3 or density >= 0.6:
            self.scores['b1_probing'] = 4
        elif count >= 1:
            self.scores['b1_probing'] = 2
        else:
            self.scores['b1_probing'] = 0
        self.justifications['b1_probing'] = "Probing question signals: {} detected (density {:.1f}/1k chars).".format(count, density)

        # Student talks — heuristic: check for "you tell me", "what do you think", student explain-back
        student_talk_signals = len(re.findall(r'(?:you tell me|can you explain|walk me through|in your own words|what do you think)', self.transcript, re.I))
        self.scores['b1_student_talks'] = 4 if student_talk_signals >= 3 else (2 if student_talk_signals >= 1 else 0)
        self.justifications['b1_student_talks'] = "Student-talk prompts: {} found.".format(student_talk_signals)

        # No remap — give credit unless heavy lecturing detected
        lecture_signals = len(re.findall(r'(?:so basically|let me explain|the answer is|what you need to know is)', self.transcript, re.I))
        self.scores['b1_no_remap'] = 3 if lecture_signals < 3 else (1 if lecture_signals < 6 else 0)
        self.justifications['b1_no_remap'] = "Lecture/remap signals: {} (fewer is better).".format(lecture_signals)

        # B2: Weakness Identification — 15 pts
        #   b2_identifies_reasons: identifies why student struggles (5 pts)
        #   b2_no_excuses: doesn't accept excuses, digs deeper (5 pts)
        #   b2_actionable: creates actionable plan for weaknesses (5 pts)
        has_weakness_id = info['weak_chem'] or info['weak_bio'] or bool(re.search(r'(?:struggle|weak|difficulty|hard time|challenge)', self.transcript, re.I))
        self.scores['b2_identifies_reasons'] = 5 if has_weakness_id else 0
        self.justifications['b2_identifies_reasons'] = "Weakness areas identified in discussion." if has_weakness_id else "No explicit weakness identification found."

        has_dig_deeper = bool(re.search(r'(?:why do you think|what makes that hard|where do you get stuck|what specifically)', self.transcript, re.I))
        self.scores['b2_no_excuses'] = 5 if has_dig_deeper else (2 if has_weakness_id else 0)
        self.justifications['b2_no_excuses'] = "Tutor probed deeper into student struggles." if has_dig_deeper else "No deep probing into struggle reasons."

        has_actionable = notes_check['below_avg_topics']['status'] != 'No' or notes_check['daily_tasks']['status'] != 'No'
        self.scores['b2_actionable'] = 5 if has_actionable else 0
        self.justifications['b2_actionable'] = "Actionable plan documented for weak areas." if has_actionable else "No actionable plan for weaknesses."

        # B3: Passage Practice — 10 pts
        #   b3_three_qs: at least 3 practice questions/passages discussed (4 pts)
        #   b3_student_teaches: student teaches back concept (3 pts)
        #   b3_paragraph_feedback: paragraph-level feedback on passage approach (3 pts)
        has_passage = bool(re.search(r'(?:passage|question\s*\d|let.?s try|practice\s*(?:question|problem))', self.transcript, re.I))
        topic_count = len(info['topics_discussed'])
        self.scores['b3_three_qs'] = 4 if topic_count >= 3 else (2 if topic_count >= 1 else 0)
        self.justifications['b3_three_qs'] = "{} topics/questions discussed.".format(topic_count)

        teach_back = bool(re.findall(r'(?:explain.*back|teach.*me|your own words|walk me through)', self.transcript, re.I))
        self.scores['b3_student_teaches'] = 3 if teach_back else 0
        self.justifications['b3_student_teaches'] = "Student teach-back detected." if teach_back else "No teach-back found."

        has_paragraph_fb = bool(re.search(r'(?:paragraph|feedback|approach.*passage|strategy.*passage)', self.transcript, re.I)) and has_passage
        self.scores['b3_paragraph_feedback'] = 3 if has_paragraph_fb else 0
        self.justifications['b3_paragraph_feedback'] = "Passage-level feedback provided." if has_paragraph_fb else "No passage-level feedback detected."

        # B4: Student Engagement — 10 pts
        #   b4_takeaways: major takeaways asked (3 pts, binary from transcript)
        #   b4_questions: student encouraged to ask questions (4 pts)
        #   b4_timing_accuracy: session timing appropriate (3 pts)
        self.scores['b4_takeaways'] = 3 if self._detect_major_takeaways() else 0
        self.justifications['b4_takeaways'] = notes_check['sop_major_takeaways']['evidence']

        has_encourage_qs = bool(re.search(r'(?:any questions|do you have questions|feel free to ask|don.t hesitate|questions for me)', self.transcript, re.I))
        self.scores['b4_questions'] = 4 if has_encourage_qs else 0
        self.justifications['b4_questions'] = "Student encouraged to ask questions." if has_encourage_qs else "No encouragement to ask questions found."

        # Timing: transcript length as proxy (30k-60k chars ~ 45-90 min is ideal)
        tlen = info['transcript_length']
        if 25000 <= tlen <= 70000:
            self.scores['b4_timing_accuracy'] = 3
        elif 15000 <= tlen < 25000 or 70000 < tlen <= 90000:
            self.scores['b4_timing_accuracy'] = 2
        else:
            self.scores['b4_timing_accuracy'] = 0
        self.justifications['b4_timing_accuracy'] = "Transcript length {} chars (proxy for session duration).".format(tlen)

        # =====================================================================
        # C. NOTES & DOCUMENTATION — 20 pts (6 binary items: 3+3+5+3+3+3)
        # =====================================================================
        self.scores['c_template_named'] = 3 if notes_check['template_named']['status'] == 'Yes' else 0
        self.justifications['c_template_named'] = notes_check['template_named']['evidence']

        self.scores['c_overview_tab'] = 3 if notes_check['overview_tab']['status'] == 'Yes' else 0
        self.justifications['c_overview_tab'] = notes_check['overview_tab']['evidence']

        # Session notes detailed — 5 pts (largest single C item)
        if notes_check['session_notes_detailed']['status'] == 'Yes':
            self.scores['c_session_notes_detailed'] = 5
        elif notes_check['session_notes_detailed']['status'] == 'Partial':
            self.scores['c_session_notes_detailed'] = 3
        else:
            self.scores['c_session_notes_detailed'] = 0
        self.justifications['c_session_notes_detailed'] = notes_check['session_notes_detailed']['evidence']

        self.scores['c_exam_progress'] = 3 if notes_check['exam_progress']['status'] == 'Yes' else 0
        self.justifications['c_exam_progress'] = notes_check['exam_progress']['evidence']

        self.scores['c_next_steps_written'] = 3 if notes_check['next_steps_written']['status'] == 'Yes' else 0
        self.justifications['c_next_steps_written'] = notes_check['next_steps_written']['evidence']

        self.scores['c_activity_tracking'] = 3 if notes_check['activity_tracking']['status'] == 'Yes' else 0
        self.justifications['c_activity_tracking'] = notes_check['activity_tracking']['evidence']

        # =====================================================================
        # D. PROFESSIONALISM — 15 pts (5 binary items: 3+3+3+3+3)
        # =====================================================================
        # d_demeanor: professional, positive tone (3 pts)
        negative_tone = bool(re.search(r'(?:that.s wrong|you.re wrong|no no no|are you serious|come on)', self.transcript, re.I))
        self.scores['d_demeanor'] = 0 if negative_tone else 3
        self.justifications['d_demeanor'] = "Negative tone detected." if negative_tone else "Professional demeanor maintained."

        # d_no_guarantees: no score guarantees made (3 pts)
        has_guarantee = bool(re.search(r'(?:guarantee|promise you.*score|definitely get a \d{3}|you will get)', self.transcript, re.I))
        self.scores['d_no_guarantees'] = 0 if has_guarantee else 3
        self.justifications['d_no_guarantees'] = "Score guarantee detected — prohibited." if has_guarantee else "No score guarantees made."

        # d_proper_channels: directs student to proper support channels (3 pts)
        proper_channels = bool(re.search(r'(?:email|reach out|contact|office hours|support|director)', self.transcript, re.I))
        self.scores['d_proper_channels'] = 3 if proper_channels else 3  # default credit unless violation
        self.justifications['d_proper_channels'] = "Proper channels referenced or no violation detected."

        # d_on_time: session started on time (3 pts) — default credit; deduct only if evidence of late start
        late_start = bool(re.search(r'(?:sorry.{0,20}late|apolog.{0,20}late|running late|started late)', self.transcript, re.I))
        self.scores['d_on_time'] = 0 if late_start else 3
        self.justifications['d_on_time'] = "Evidence of late start." if late_start else "No evidence of late start."

        # d_approved_platforms: used approved platforms (3 pts) — default credit
        unapproved = bool(re.search(r'(?:whatsapp|personal\s*phone|text\s*me|my\s*cell)', self.transcript, re.I))
        self.scores['d_approved_platforms'] = 0 if unapproved else 3
        self.justifications['d_approved_platforms'] = "Unapproved communication platform referenced." if unapproved else "Approved platforms used."

        # =====================================================================
        # TOTALS & RATING
        # =====================================================================
        a_total = (self.scores['a1_structure'] + self.scores['a2_schedule']
                   + self.scores['a2_fl_exams'] + self.scores['a2_aamc']
                   + self.scores['a3_presession'] + self.scores['a3_survey']
                   + self.scores['a3_postsession_notes'] + self.scores['a3_shared']
                   + self.scores['a4_specific'])
        b_total = (self.scores['b1_probing'] + self.scores['b1_student_talks']
                   + self.scores['b1_no_remap']
                   + self.scores['b2_identifies_reasons'] + self.scores['b2_no_excuses']
                   + self.scores['b2_actionable']
                   + self.scores['b3_three_qs'] + self.scores['b3_student_teaches']
                   + self.scores['b3_paragraph_feedback']
                   + self.scores['b4_takeaways'] + self.scores['b4_questions']
                   + self.scores['b4_timing_accuracy'])
        c_total = (self.scores['c_template_named'] + self.scores['c_overview_tab']
                   + self.scores['c_session_notes_detailed'] + self.scores['c_exam_progress']
                   + self.scores['c_next_steps_written'] + self.scores['c_activity_tracking'])
        d_total = (self.scores['d_demeanor'] + self.scores['d_no_guarantees']
                   + self.scores['d_proper_channels'] + self.scores['d_on_time']
                   + self.scores['d_approved_platforms'])
        raw_total = a_total + b_total + c_total + d_total

        if raw_total >= 120:
            rating = 'Excellent'
        elif raw_total >= 100:
            rating = 'Satisfactory'
        elif raw_total >= 80:
            rating = 'Needs Improvement'
        else:
            rating = 'Unsatisfactory'

        self.findings = {
            'info': info,
            'notes_check': notes_check,
            'scores': self.scores,
            'a_total': a_total,
            'b_total': b_total,
            'c_total': c_total,
            'd_total': d_total,
            'raw_total': raw_total,
            'overall_rating': rating,
        }
        return self.findings
    
    def _get_biggest_risk(self):
        """Determine the biggest risk based on 4-category scores."""
        a_total = self.findings.get('a_total', 0)
        b_total = self.findings.get('b_total', 0)
        c_total = self.findings.get('c_total', 0)
        d_total = self.findings.get('d_total', 0)

        if a_total < 25:
            return "A. SOP Compliance is critically low — study schedule, exam planning, and session requirements are largely missing."
        if self.scores.get('b4_takeaways', 0) == 0:
            return "Required closing missing: tutor did not ask 'What were your major takeaways?' in the final portion of the session."
        if b_total < 25:
            return "B. Coaching Quality gaps — Socratic method, weakness identification, or passage practice need improvement."
        if c_total < 10:
            return "C. Notes & Documentation is weak — session notes, exam progress tracking, or next steps are missing."
        if d_total < 10:
            return "D. Professionalism concern — check demeanor, guarantees, punctuality, or platform compliance."
        return "Minor documentation and coaching gaps may impact student's ability to follow the study plan independently."
    
    def _get_top_fixes(self):
        """Generate top 3 fixes based on lowest scores across A/B/C/D categories."""
        fixes = []
        if self.scores.get('a2_fl_exams', 0) < 4:
            fixes.append("Document FL exam schedule with all 10 dates (JW FL 1-6 + AAMC exams) in notes")
        if self.scores.get('a2_aamc', 0) < 4:
            fixes.append("Schedule AAMC question packs/resources (if student has them) with deadlines in the study plan")
        if self.scores.get('b4_takeaways', 0) == 0:
            fixes.append("Required closing: Ask 'What were your major takeaways?' at session end (all 515+, Intensive, CARS sessions)")
        if self.scores.get('a4_specific', 0) < 8:
            fixes.append("Address session-specific requirements: below-avg topics, next session date, strategy notes")
        if self.scores.get('a2_schedule', 0) == 0:
            fixes.append("Create a study schedule with weekly checklist and Week 1 daily tasks")
        if self.scores.get('b1_probing', 0) < 4:
            fixes.append("Use more Socratic/probing questions; have student explain back rather than lecturing")
        if self.scores.get('c_session_notes_detailed', 0) < 3:
            fixes.append("Write detailed session notes covering discussion points and action items")
        return fixes[:3]
    
    def _generate_gap_analysis(self):
        """Generate transcript vs notes gap analysis aligned with A/B/C/D categories."""
        info = self.findings['info']

        gap_items = [
            ('A: Test date: ' + info['test_date'], info['test_date'] != 'Not found', 'No'),
            ('A: Baseline score: ~' + info['baseline_score'], info['baseline_score'] != 'Not found', 'No'),
            ('A: Target score: ' + info['target_score'], info['target_score'] != 'Not found', 'No'),
            ('A: Student constraints (classes, accommodations)', info['has_classes'] or info['has_adhd'], 'No'),
            ('A: Weak areas identified', info['weak_chem'] or info['weak_bio'], 'No'),
            ('A: FL exam schedule (10 exams: JW FL + AAMC)', info['has_fl_discussion'], 'No'),
            ('A: AAMC question packs/resources scheduling', info.get('has_aamc_qpacks', info['has_aamc']), 'No'),
            ('B: Probing / Socratic questions used', self.scores.get('b1_probing', 0) > 0, 'Partial' if self.scores.get('b1_probing', 0) > 0 else 'No'),
            ('B: Student teach-back observed', self.scores.get('b3_student_teaches', 0) > 0, 'No'),
        ]

        for topic in info['topics_discussed']:
            gap_items.append(('B: ' + topic + ' strategy', True, 'Partial'))

        gap_items.append(('B: Major takeaways closing', self._detect_major_takeaways(), 'No'))
        gap_items.append(('A: Next session timing', info['has_next_session'], 'No'))

        return gap_items
    
    def _generate_tutor_feedback(self):
        """Generate detailed tutor feedback aligned with A/B/C/D categories."""
        info = self.findings['info']
        notes_check = self.findings['notes_check']

        # What went well
        positives = []
        if info['has_strategy'] and len(info['topics_discussed']) >= 2:
            positives.append(("Strong Content Instruction (B)", "Multiple topics were covered with evident strategy discussion. This demonstrates good session utilization and content expertise."))
        if info['has_adhd'] or info['has_classes']:
            positives.append(("Awareness of Student Context (A)", "You acknowledged the student's personal constraints and circumstances, which builds rapport and trust."))
        if info['transcript_length'] > 30000:
            positives.append(("Thorough Session (B)", "The substantial session length indicates comprehensive coverage rather than rushing through material."))
        if info['has_next_session']:
            positives.append(("Forward Planning (A)", "Discussion of next session timing shows continuity planning."))
        if len(info['topics_discussed']) >= 3:
            positives.append(("Multi-Topic Coverage (B)", "Covered {} distinct topic areas: {}".format(len(info['topics_discussed']), ', '.join(info['topics_discussed']))))
        if self.scores.get('b1_probing', 0) >= 6:
            positives.append(("Strong Socratic Method (B1)", "Good use of probing questions to guide student thinking."))
        if self.findings.get('d_total', 0) >= 12:
            positives.append(("Professional Conduct (D)", "Professional demeanor, punctuality, and platform compliance all met."))

        if not positives:
            positives.append(("Session Completed", "Session was held and covered material with the student."))

        # Areas for improvement
        improvements = []
        a_total = self.findings.get('a_total', 0)

        if a_total < 25:
            improvements.append({
                'title': 'Critical: A. SOP Compliance Gaps',
                'what': 'Multiple required SOP items are missing or partial (study schedule, FL exam planning, session-specific requirements).',
                'why': 'Student needs a complete take-home document and a clear session close. Without it, they cannot follow the plan independently.',
                'fix': 'Create a Google Doc with Student Snapshot, FL Exam Schedule (10 exams: JW FL 1-6 + AAMC exams), AAMC Question Pack scheduling (if student has them), Weekly Checklist, Week 1 Daily Tasks, Strategy Summary. End every session by asking: "What were your major takeaways?"'
            })

        if notes_check['fl_exam_schedule']['status'] == 'No':
            improvements.append({
                'title': 'Missing: FL Exam Schedule (A2)',
                'what': 'FL sequencing may have been discussed verbally but was not documented with specific dates.',
                'why': 'Student needs clarity on which test to take each week. Without a documented schedule, they may sequence incorrectly.',
                'fix': 'Create a table: Week | Date | Exam | Notes. Be explicit with dates. Include the test date as the anchor.'
            })

        if notes_check['below_avg_topics']['status'] == 'No':
            improvements.append({
                'title': 'Missing: Below-Average Topic Prioritization (A4)',
                'what': 'Weak areas may have been identified through discussion but no prioritized topic list was created in notes.',
                'why': 'Student needs specific topics to focus on. Without this list, they may study inefficiently.',
                'fix': 'Create a "Priority Topics" section organized by MCAT section. Exclude topics covered by live course. Rank by importance.'
            })

        if self.scores.get('b1_probing', 0) < 4:
            improvements.append({
                'title': 'Improve: Socratic Method (B1)',
                'what': 'Few probing questions detected. Tutor may be lecturing more than guiding.',
                'why': 'Students retain more when they arrive at answers through guided questioning.',
                'fix': 'Use prompts like "What do you think?", "Walk me through your reasoning", "Can you explain that in your own words?"'
            })

        if self.scores.get('b4_takeaways', 0) == 0:
            improvements.append({
                'title': 'Required: Major Takeaways Closing (B4)',
                'what': 'Tutor did not ask the student about their major takeaways in the final portion of the session.',
                'why': 'This closing is required for all 515+, Intensive, and CARS sessions to reinforce learning.',
                'fix': 'In the last 5-10 minutes, ask: "What were your major takeaways from today?" or similar.'
            })

        if self.findings.get('c_total', 0) < 10:
            improvements.append({
                'title': 'Improve: C. Notes & Documentation',
                'what': 'Session notes, exam progress tracking, or next steps are missing or incomplete.',
                'why': 'Documented notes are the "product" the student takes home; they reference it daily.',
                'fix': 'Use the standard template. Fill in overview, session notes, exam progress, next steps, and activity tracking sections.'
            })

        return positives, improvements
    
    def generate_report(self):
        """Generate the full comprehensive grading report using 4-category 135-point format."""
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
Score: {raw_total}/135 (A: {a_total}/50 | B: {b_total}/50 | C: {c_total}/20 | D: {d_total}/15)
Biggest Risk: {risk}

Top 3 Fixes
""".format(
            student=self.student_name,
            tutor=self.tutor_name,
            date=self.session_date,
            test_date=info['test_date'],
            rating=f['overall_rating'].upper(),
            raw_total=f['raw_total'],
            a_total=f['a_total'],
            b_total=f['b_total'],
            c_total=f['c_total'],
            d_total=f['d_total'],
            risk=self._get_biggest_risk(),
            sep=sep
        )

        for i, fix in enumerate(self._get_top_fixes(), 1):
            clean_fix = fix.replace('**', '')
            report += "{}. {}\n".format(i, clean_fix)

        # --- Category A: SOP Compliance (50 pts) ---
        report += """
{sep}

CATEGORY A: SOP COMPLIANCE (50 pts)

Item                                                | Score | Max | Justification
----------------------------------------------------|-------|-----|--------------------------------------------
A1  Session Structure & Timing                      | {a1:2}    | 10  | {a1_j}
A2a Study Schedule created                          | {a2s:2}    |  6  | {a2s_j}
A2b FL Exam schedule with dates                     | {a2f:2}    |  4  | {a2f_j}
A2c AAMC materials scheduled                        | {a2a:2}    |  4  | {a2a_j}
A3a Pre-session preparation                         | {a3p:2}    |  4  | {a3p_j}
A3b Student survey / baseline                       | {a3s:2}    |  4  | {a3s_j}
A3c Post-session notes written                      | {a3n:2}    |  2  | {a3n_j}
A3d Documentation shared                            | {a3d:2}    |  2  | {a3d_j}
A4  Session-specific requirements                   | {a4:2}    | 14  | {a4_j}
----------------------------------------------------|-------|-----|--------------------------------------------
A SUBTOTAL                                          | {a_total:2}    | 50  |
""".format(
            a1=self.scores['a1_structure'], a1_j=self.justifications.get('a1_structure', ''),
            a2s=self.scores['a2_schedule'], a2s_j=self.justifications.get('a2_schedule', ''),
            a2f=self.scores['a2_fl_exams'], a2f_j=self.justifications.get('a2_fl_exams', '')[:60],
            a2a=self.scores['a2_aamc'], a2a_j=self.justifications.get('a2_aamc', '')[:60],
            a3p=self.scores['a3_presession'], a3p_j=self.justifications.get('a3_presession', ''),
            a3s=self.scores['a3_survey'], a3s_j=self.justifications.get('a3_survey', ''),
            a3n=self.scores['a3_postsession_notes'], a3n_j=self.justifications.get('a3_postsession_notes', ''),
            a3d=self.scores['a3_shared'], a3d_j=self.justifications.get('a3_shared', ''),
            a4=self.scores['a4_specific'], a4_j=self.justifications.get('a4_specific', ''),
            a_total=f['a_total'],
            sep=sep
        )

        # --- Category B: Coaching Quality (50 pts) ---
        report += """
{sep}

CATEGORY B: COACHING QUALITY (50 pts)

Item                                                | Score | Max | Justification
----------------------------------------------------|-------|-----|--------------------------------------------
B1a Probing questions (Socratic)                    | {b1p:2}    |  8  | {b1p_j}
B1b Student does the talking                        | {b1s:2}    |  4  | {b1s_j}
B1c No re-explain / lecturing                       | {b1n:2}    |  3  | {b1n_j}
B2a Identifies reasons for struggles                | {b2i:2}    |  5  | {b2i_j}
B2b Digs deeper, no excuses accepted                | {b2n:2}    |  5  | {b2n_j}
B2c Actionable plan for weaknesses                  | {b2a:2}    |  5  | {b2a_j}
B3a 3+ practice questions/passages                  | {b3q:2}    |  4  | {b3q_j}
B3b Student teaches back concept                    | {b3t:2}    |  3  | {b3t_j}
B3c Passage-level feedback                          | {b3f:2}    |  3  | {b3f_j}
B4a Major takeaways asked                           | {b4t:2}    |  3  | {b4t_j}
B4b Student encouraged to ask questions             | {b4q:2}    |  4  | {b4q_j}
B4c Session timing appropriate                      | {b4ti:2}    |  3  | {b4ti_j}
----------------------------------------------------|-------|-----|--------------------------------------------
B SUBTOTAL                                          | {b_total:2}    | 50  |
""".format(
            b1p=self.scores['b1_probing'], b1p_j=self.justifications.get('b1_probing', '')[:60],
            b1s=self.scores['b1_student_talks'], b1s_j=self.justifications.get('b1_student_talks', ''),
            b1n=self.scores['b1_no_remap'], b1n_j=self.justifications.get('b1_no_remap', ''),
            b2i=self.scores['b2_identifies_reasons'], b2i_j=self.justifications.get('b2_identifies_reasons', ''),
            b2n=self.scores['b2_no_excuses'], b2n_j=self.justifications.get('b2_no_excuses', ''),
            b2a=self.scores['b2_actionable'], b2a_j=self.justifications.get('b2_actionable', ''),
            b3q=self.scores['b3_three_qs'], b3q_j=self.justifications.get('b3_three_qs', ''),
            b3t=self.scores['b3_student_teaches'], b3t_j=self.justifications.get('b3_student_teaches', ''),
            b3f=self.scores['b3_paragraph_feedback'], b3f_j=self.justifications.get('b3_paragraph_feedback', ''),
            b4t=self.scores['b4_takeaways'], b4t_j=self.justifications.get('b4_takeaways', '')[:60],
            b4q=self.scores['b4_questions'], b4q_j=self.justifications.get('b4_questions', ''),
            b4ti=self.scores['b4_timing_accuracy'], b4ti_j=self.justifications.get('b4_timing_accuracy', ''),
            b_total=f['b_total'],
            sep=sep
        )

        # --- Category C: Notes & Documentation (20 pts) ---
        report += """
{sep}

CATEGORY C: NOTES & DOCUMENTATION (20 pts)

Item                                                | Score | Max | Justification
----------------------------------------------------|-------|-----|--------------------------------------------
C1  Template properly named                         | {c1:2}    |  3  | {c1_j}
C2  Overview tab present                            | {c2:2}    |  3  | {c2_j}
C3  Session notes detailed                          | {c3:2}    |  5  | {c3_j}
C4  Exam progress tracked                           | {c4:2}    |  3  | {c4_j}
C5  Next steps written                              | {c5:2}    |  3  | {c5_j}
C6  Activity tracking present                       | {c6:2}    |  3  | {c6_j}
----------------------------------------------------|-------|-----|--------------------------------------------
C SUBTOTAL                                          | {c_total:2}    | 20  |
""".format(
            c1=self.scores['c_template_named'], c1_j=self.justifications.get('c_template_named', '')[:60],
            c2=self.scores['c_overview_tab'], c2_j=self.justifications.get('c_overview_tab', '')[:60],
            c3=self.scores['c_session_notes_detailed'], c3_j=self.justifications.get('c_session_notes_detailed', '')[:60],
            c4=self.scores['c_exam_progress'], c4_j=self.justifications.get('c_exam_progress', '')[:60],
            c5=self.scores['c_next_steps_written'], c5_j=self.justifications.get('c_next_steps_written', '')[:60],
            c6=self.scores['c_activity_tracking'], c6_j=self.justifications.get('c_activity_tracking', '')[:60],
            c_total=f['c_total'],
            sep=sep
        )

        # --- Category D: Professionalism (15 pts) ---
        report += """
{sep}

CATEGORY D: PROFESSIONALISM (15 pts)

Item                                                | Score | Max | Justification
----------------------------------------------------|-------|-----|--------------------------------------------
D1  Professional demeanor                           | {d1:2}    |  3  | {d1_j}
D2  No score guarantees                             | {d2:2}    |  3  | {d2_j}
D3  Proper channels referenced                      | {d3:2}    |  3  | {d3_j}
D4  On time                                         | {d4:2}    |  3  | {d4_j}
D5  Approved platforms used                         | {d5:2}    |  3  | {d5_j}
----------------------------------------------------|-------|-----|--------------------------------------------
D SUBTOTAL                                          | {d_total:2}    | 15  |
""".format(
            d1=self.scores['d_demeanor'], d1_j=self.justifications.get('d_demeanor', ''),
            d2=self.scores['d_no_guarantees'], d2_j=self.justifications.get('d_no_guarantees', ''),
            d3=self.scores['d_proper_channels'], d3_j=self.justifications.get('d_proper_channels', ''),
            d4=self.scores['d_on_time'], d4_j=self.justifications.get('d_on_time', ''),
            d5=self.scores['d_approved_platforms'], d5_j=self.justifications.get('d_approved_platforms', ''),
            d_total=f['d_total'],
            sep=sep
        )

        # --- SOP Evidence section ---
        report += """
{sep}

SOP EVIDENCE (NOTES-BASED)

SOP Item                                          | Present? | Evidence
--------------------------------------------------|----------|--------------------------------------------------
Full-Length Exam schedule (10 FLs)                | {exam_status:8} | {exam_ev}
AAMC Question Packs/Resources                     | {aamc_status:8} | {aamc_ev}
Below-average topics                              | {topics_status:8} | {topics_ev}
Weekly checklist                                  | {weekly_status:8} | {weekly_ev}
Daily tasks for Week 1                            | {daily_status:8} | {daily_ev}
Strategy portion notes                            | {strat_status:8} | {strat_ev}
Next session date                                 | {next_status:8} | {next_ev}
Major takeaways closing                           | {takeaways_status:8} | {takeaways_ev}
Google Doc shared                                 | {doc_status:8} | {doc_ev}
Baseline documented                               | {base_status:8} | {base_ev}

{sep}

TRANSCRIPT VS. NOTES GAP ANALYSIS

Topic Discussed                                           | In Notes?
----------------------------------------------------------|----------
""".format(
            exam_status=notes_check['fl_exam_schedule']['status'],
            exam_ev=(notes_check['fl_exam_schedule']['evidence'] or '')[:50],
            aamc_status=notes_check['aamc_question_packs']['status'],
            aamc_ev=(notes_check['aamc_question_packs']['evidence'] or '')[:50],
            topics_status=notes_check['below_avg_topics']['status'],
            topics_ev=(notes_check['below_avg_topics']['evidence'] or '')[:50],
            weekly_status=notes_check['weekly_checklist']['status'],
            weekly_ev=(notes_check['weekly_checklist']['evidence'] or '')[:50],
            daily_status=notes_check['daily_tasks']['status'],
            daily_ev=(notes_check['daily_tasks']['evidence'] or '')[:50],
            strat_status=notes_check['strategy_notes']['status'],
            strat_ev=(notes_check['strategy_notes']['evidence'] or '')[:50],
            next_status=notes_check['next_session']['status'],
            next_ev=(notes_check['next_session']['evidence'] or '')[:50],
            takeaways_status=notes_check.get('sop_major_takeaways', {}).get('status', 'No'),
            takeaways_ev=(notes_check.get('sop_major_takeaways', {}).get('evidence', '') or '')[:50],
            doc_status=notes_check['google_doc_shared']['status'],
            doc_ev=(notes_check['google_doc_shared']['evidence'] or '')[:50],
            base_status=notes_check['baseline_documented']['status'],
            base_ev=(notes_check['baseline_documented']['evidence'] or '')[:50],
            sep=sep
        )

        for topic, discussed, in_notes in gap_items:
            if discussed:
                report += "{:57} | {}\n".format(topic[:57], in_notes)

        report += """
{sep}

RECOMMENDED NOTES REWRITE (NOTES V2)

Given that multiple critical SOP items are missing from notes, below is a recommended rewrite.

{sep}

{notes_v2}

{sep}

TUTOR FEEDBACK

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

Category                                     | Score | Max
---------------------------------------------|-------|-----
A. SOP Compliance                            | {a_total:2}    | 50
  A1 Session Structure & Timing              | {a1:2}    | 10
  A2 Study Schedule & Exam Planning          | {a2_total:2}    | 14
  A3 Pre/Post-Session Tasks                  | {a3_total:2}    | 12
  A4 Session-Specific Requirements           | {a4:2}    | 14
B. Coaching Quality                          | {b_total:2}    | 50
  B1 Socratic Method                         | {b1_total:2}    | 15
  B2 Weakness Identification                 | {b2_total:2}    | 15
  B3 Passage Practice                        | {b3_total:2}    | 10
  B4 Student Engagement                      | {b4_total:2}    | 10
C. Notes & Documentation                    | {c_total:2}    | 20
D. Professionalism                           | {d_total:2}    | 15
---------------------------------------------|-------|-----
RAW TOTAL                                    | {raw_total:3}   | 135

Overall Rating: {rating}
Grade Scale: 120-135 Excellent | 100-119 Satisfactory | 80-99 Needs Improvement | <80 Unsatisfactory

Summary:
{summary}

Recommended Actions:
1. Tutor should immediately create and share a comprehensive Session 1 Google Doc (see Notes v2 above)
2. Confirm next session date in writing; close every session with "What were your major takeaways?"
3. Future sessions should include 5-10 minutes at end for documentation review with student

{sep}

Graded by: JW Session Notes Grader Agent
Grading Agent Version: 3.0 (135-point 4-category architecture)
Reference Documents: first_session_sop_agent.md, grading_first_session_agent.md, session_1_grading_agent.md
""".format(
            tutor=self.tutor_name.split()[0] if self.tutor_name else 'Tutor',
            a_total=f['a_total'],
            a1=self.scores['a1_structure'],
            a2_total=self.scores['a2_schedule'] + self.scores['a2_fl_exams'] + self.scores['a2_aamc'],
            a3_total=self.scores['a3_presession'] + self.scores['a3_survey'] + self.scores['a3_postsession_notes'] + self.scores['a3_shared'],
            a4=self.scores['a4_specific'],
            b_total=f['b_total'],
            b1_total=self.scores['b1_probing'] + self.scores['b1_student_talks'] + self.scores['b1_no_remap'],
            b2_total=self.scores['b2_identifies_reasons'] + self.scores['b2_no_excuses'] + self.scores['b2_actionable'],
            b3_total=self.scores['b3_three_qs'] + self.scores['b3_student_teaches'] + self.scores['b3_paragraph_feedback'],
            b4_total=self.scores['b4_takeaways'] + self.scores['b4_questions'] + self.scores['b4_timing_accuracy'],
            c_total=f['c_total'],
            d_total=f['d_total'],
            raw_total=f['raw_total'],
            rating=f['overall_rating'],
            summary=self._generate_summary(),
            sep=sep
        )

        return report
    
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

Practice Exam Schedule (11 Total)

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
    
    def _generate_summary(self):
        raw = self.findings.get('raw_total', 0)
        if raw >= 120:
            return "Excellent session with comprehensive documentation and strong coaching across all four categories. All major SOP items are addressed and the student has clear direction."
        elif raw >= 100:
            return "Satisfactory session with adequate performance. Minor improvements recommended. Grade scale: 120-135 Excellent, 100-119 Satisfactory, 80-99 Needs Improvement, <80 Unsatisfactory."
        elif raw >= 80:
            return "The tutoring session content appears solid based on transcript analysis. However, gaps exist in one or more categories (SOP compliance, coaching quality, notes, or professionalism). Review category-level feedback to target improvements."
        else:
            return "Significant gaps identified across categories. The session requires immediate follow-up: create comprehensive session notes, confirm next session date, improve Socratic questioning, and close every session by asking 'What were your major takeaways?'"


def send_email(to_emails, subject, body):
    """Send email using SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("Email not configured - skipping send")
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


def get_html():
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session Grader | Jack Westin</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
            background: #f8f9fc; 
            min-height: 100vh; 
            color: #1a1f36;
            line-height: 1.6;
        }
        .header {
            background: #fff;
            border-bottom: 1px solid #e6e9f0;
            padding: 16px 24px;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-content {
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .logo {
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, #6C5CE7 0%, #a29bfe 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: 700;
            font-size: 16px;
        }
        .header-title {
            font-size: 18px;
            font-weight: 600;
            color: #1a1f36;
        }
        .container { 
            max-width: 900px; 
            margin: 0 auto; 
            padding: 40px 24px 60px;
        }
        .page-header {
            text-align: center;
            margin-bottom: 40px;
        }
        .page-label {
            font-size: 14px;
            font-weight: 600;
            color: #6C5CE7;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        h1 { 
            font-size: 42px;
            font-weight: 700;
            color: #1a1f36;
            margin-bottom: 16px;
            letter-spacing: -0.5px;
        }
        .subtitle { 
            color: #697386; 
            font-size: 18px;
            max-width: 500px;
            margin: 0 auto;
        }
        .card { 
            background: #fff; 
            border-radius: 16px; 
            padding: 36px; 
            box-shadow: 0 4px 24px rgba(0,0,0,0.06);
            border: 1px solid #e6e9f0;
        }
        .form-group { margin-bottom: 24px; }
        label { 
            display: block; 
            font-weight: 600; 
            margin-bottom: 8px; 
            font-size: 14px;
            color: #1a1f36;
        }
        input, textarea, select { 
            width: 100%; 
            padding: 14px 16px; 
            border: 1px solid #e6e9f0; 
            border-radius: 10px; 
            font-size: 15px; 
            box-sizing: border-box;
            font-family: inherit;
            transition: border-color 0.2s, box-shadow 0.2s;
            background: #fff;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #6C5CE7;
            box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.1);
        }
        input::placeholder, textarea::placeholder {
            color: #9ca3b4;
        }
        textarea { 
            height: 200px; 
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            line-height: 1.5;
            resize: vertical;
        }
        select { cursor: pointer; }
        .row { display: flex; gap: 20px; }
        .row .form-group { flex: 1; }
        .btn { 
            width: 100%; 
            padding: 16px 32px; 
            background: linear-gradient(135deg, #6C5CE7 0%, #a29bfe 100%);
            color: #fff; 
            border: none; 
            border-radius: 50px; 
            font-size: 16px; 
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            font-family: inherit;
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(108, 92, 231, 0.35);
        }
        .btn:active {
            transform: translateY(0);
        }
        .btn:disabled { 
            background: #d1d5e0; 
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .btn-secondary { 
            background: #fff;
            color: #6C5CE7;
            border: 2px solid #6C5CE7;
        }
        .btn-secondary:hover { 
            background: #f8f7ff;
            box-shadow: 0 4px 12px rgba(108, 92, 231, 0.15);
        }
        .btn-small { 
            padding: 12px 20px; 
            font-size: 14px; 
            width: auto;
            border-radius: 8px;
        }
        .result { 
            margin-top: 24px; 
            padding: 20px; 
            border-radius: 12px; 
            display: none;
            font-size: 15px;
        }
        .result.success { 
            background: #ecfdf5; 
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        .result.error { 
            background: #fef2f2; 
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        .result.warning { 
            background: #fffbeb; 
            color: #92400e;
            border: 1px solid #fde68a;
        }
        pre { 
            background: #f8f9fc; 
            padding: 20px; 
            border-radius: 12px; 
            overflow-x: auto; 
            white-space: pre-wrap; 
            font-size: 12px; 
            max-height: 600px; 
            overflow-y: auto;
            border: 1px solid #e6e9f0;
            font-family: 'Monaco', 'Menlo', monospace;
            line-height: 1.6;
        }
        .loading { 
            display: none; 
            text-align: center; 
            padding: 40px;
        }
        .spinner { 
            border: 3px solid #e6e9f0; 
            border-top: 3px solid #6C5CE7; 
            border-radius: 50%; 
            width: 44px; 
            height: 44px; 
            animation: spin 0.8s linear infinite; 
            margin: 0 auto 16px;
        }
        .loading p {
            color: #697386;
            font-size: 15px;
        }
        @keyframes spin { 
            0% { transform: rotate(0deg); } 
            100% { transform: rotate(360deg); } 
        }
        .mode-toggle { 
            display: flex; 
            gap: 12px; 
            margin-bottom: 24px;
        }
        .mode-toggle label { 
            display: flex; 
            align-items: center; 
            gap: 8px; 
            cursor: pointer; 
            padding: 14px 20px; 
            border: 2px solid #e6e9f0; 
            border-radius: 10px; 
            font-weight: 500; 
            transition: all 0.2s;
            flex: 1;
            justify-content: center;
        }
        .mode-toggle input[type="radio"] { 
            width: auto; 
            margin: 0;
            accent-color: #6C5CE7;
        }
        .mode-toggle label:has(input:checked) { 
            border-color: #6C5CE7; 
            background: #f8f7ff;
            color: #6C5CE7;
        }
        .transcript-section { display: none; }
        .transcript-section.active { display: block; }
        .fathom-controls { 
            display: flex; 
            gap: 12px; 
            align-items: flex-end; 
            margin-bottom: 16px;
        }
        .fathom-controls .form-group { flex: 1; margin-bottom: 0; }
        .fathom-status { 
            font-size: 13px; 
            color: #697386; 
            margin-top: 12px;
            padding: 12px 16px;
            background: #f8f9fc;
            border-radius: 8px;
        }
        .fathom-status.error { 
            color: #991b1b;
            background: #fef2f2;
        }
        .fathom-status.success { 
            color: #065f46;
            background: #ecfdf5;
        }
        .recording-info { 
            background: #f8f9fc; 
            padding: 16px; 
            border-radius: 10px; 
            margin-top: 16px; 
            font-size: 14px;
            border: 1px solid #e6e9f0;
        }
        .recording-info strong { 
            display: block; 
            margin-bottom: 8px;
            color: #1a1f36;
            font-size: 15px;
        }
        @media (max-width: 640px) {
            .row { flex-direction: column; gap: 0; }
            h1 { font-size: 32px; }
            .card { padding: 24px; }
            .mode-toggle { flex-direction: column; }
            .fathom-controls { flex-direction: column; }
            .fathom-controls .btn-small { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">JW</div>
            <div class="header-title">Session Grader</div>
        </div>
    </div>
    <div class="container">
        <div class="page-header">
            <div class="page-label">Quality Assurance Tool</div>
            <h1>Session Notes Grader</h1>
            <p class="subtitle">Evaluate tutoring session quality with comprehensive, actionable feedback</p>
        </div>
        <div class="card">
            <form id="gradeForm">
                <div class="row">
                    <div class="form-group">
                        <label>Student Name</label>
                        <input type="text" id="studentName" required placeholder="e.g., Anji Herman">
                    </div>
                    <div class="form-group">
                        <label>Tutor Name</label>
                        <input type="text" id="tutorName" required placeholder="e.g., Ian Abrams">
                    </div>
                </div>
                <div class="row">
                    <div class="form-group">
                        <label>Tutor Email</label>
                        <input type="email" id="tutorEmail" required placeholder="tutor@jackwestin.com">
                    </div>
                    <div class="form-group">
                        <label>Session Date</label>
                        <input type="date" id="sessionDate" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Transcript Source</label>
                    <div class="mode-toggle">
                        <label>
                            <input type="radio" name="transcriptMode" value="paste" checked onchange="switchMode('paste')">
                            Paste Transcript
                        </label>
                        <label>
                            <input type="radio" name="transcriptMode" value="fathom" onchange="switchMode('fathom')">
                            Pull from Fathom
                        </label>
                    </div>
                </div>
                
                <div id="pasteSection" class="transcript-section active">
                    <div class="form-group">
                        <label>Paste Transcript</label>
                        <textarea id="transcript" placeholder="Paste the full session transcript here..."></textarea>
                    </div>
                </div>
                
                <div id="fathomSection" class="transcript-section">
                    <div class="fathom-controls">
                        <div class="form-group">
                            <label>Select Recording</label>
                            <select id="recordingSelect" onchange="onRecordingSelect()">
                                <option value="">-- Click "Load Recordings" first --</option>
                            </select>
                        </div>
                        <button type="button" class="btn btn-secondary btn-small" id="loadRecordingsBtn" onclick="loadRecordings()">
                            Load Recordings
                        </button>
                    </div>
                    <div id="fathomStatus" class="fathom-status"></div>
                    <div id="recordingInfo" class="recording-info" style="display:none;"></div>
                    <input type="hidden" id="recordingId" value="">
                </div>
                
                <button type="submit" class="btn" id="submitBtn">Grade Session & Send Report</button>
            </form>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p id="loadingText">Analyzing transcript and generating comprehensive report...</p>
            </div>
            <div class="result" id="result"></div>
            <pre id="report" style="display:none;"></pre>
        </div>
    </div>
    <script>
        var currentMode = 'paste';
        var recordings = [];
        var fathomConfigured = false;
        
        document.getElementById('sessionDate').valueAsDate = new Date();
        
        function switchMode(mode) {
            currentMode = mode;
            document.getElementById('pasteSection').classList.toggle('active', mode === 'paste');
            document.getElementById('fathomSection').classList.toggle('active', mode === 'fathom');
            
            if (mode === 'fathom') {
                checkFathomStatus();
            }
        }
        
        async function checkFathomStatus() {
            var status = document.getElementById('fathomStatus');
            try {
                var resp = await fetch('/api/fathom-status');
                var json = await resp.json();
                fathomConfigured = json.configured;
                if (!json.configured) {
                    status.className = 'fathom-status error';
                    status.textContent = 'Fathom API key not configured. Please add FATHOM_API_KEY to environment variables.';
                    document.getElementById('loadRecordingsBtn').disabled = true;
                } else {
                    status.className = 'fathom-status success';
                    status.textContent = 'Fathom API connected. Click "Load Recordings" to fetch your recordings.';
                    document.getElementById('loadRecordingsBtn').disabled = false;
                }
            } catch(err) {
                status.className = 'fathom-status error';
                status.textContent = 'Error checking Fathom status: ' + err.message;
            }
        }
        
        async function loadRecordings() {
            var status = document.getElementById('fathomStatus');
            var select = document.getElementById('recordingSelect');
            var btn = document.getElementById('loadRecordingsBtn');
            
            btn.disabled = true;
            btn.textContent = 'Loading...';
            status.className = 'fathom-status';
            status.textContent = 'Fetching recordings from Fathom...';
            
            try {
                var resp = await fetch('/api/list-recordings');
                var json = await resp.json();
                
                if (json.success) {
                    recordings = json.recordings;
                    select.innerHTML = '<option value="">-- Select a recording --</option>';
                    
                    recordings.forEach(function(rec) {
                        var opt = document.createElement('option');
                        opt.value = rec.id;
                        var title = rec.title || 'Untitled';
                        var date = rec.date || 'Unknown date';
                        var participants = rec.participants ? rec.participants.join(', ') : '';
                        opt.textContent = title + ' (' + date + ')' + (participants ? ' - ' + participants : '');
                        select.appendChild(opt);
                    });
                    
                    status.className = 'fathom-status success';
                    status.textContent = 'Found ' + recordings.length + ' recordings. Select one to grade.';
                } else {
                    status.className = 'fathom-status error';
                    status.textContent = 'Error: ' + json.error;
                }
            } catch(err) {
                status.className = 'fathom-status error';
                status.textContent = 'Error loading recordings: ' + err.message;
            }
            
            btn.disabled = false;
            btn.textContent = 'Load Recordings';
        }
        
        async function onRecordingSelect() {
            var select = document.getElementById('recordingSelect');
            var infoDiv = document.getElementById('recordingInfo');
            var recordingIdInput = document.getElementById('recordingId');
            var status = document.getElementById('fathomStatus');
            
            var selectedId = select.value;
            recordingIdInput.value = selectedId;
            
            if (selectedId) {
                var rec = recordings.find(function(r) { return r.id === selectedId; });
                if (rec) {
                    var durationMins = rec.duration ? Math.round(rec.duration / 60) : 0;
                    infoDiv.innerHTML = '<strong>' + (rec.title || 'Untitled') + '</strong><br>' +
                        'Date: ' + (rec.date || 'Unknown') + '<br>' +
                        'Duration: ' + durationMins + ' minutes<br>' +
                        'Participants: ' + (rec.participants ? rec.participants.join(', ') : 'Unknown') + 
                        '<br><br><em>Loading transcript preview...</em>';
                    infoDiv.style.display = 'block';
                    
                    // Fetch transcript preview
                    try {
                        var resp = await fetch('/api/get-transcript?recording_id=' + encodeURIComponent(selectedId));
                        var json = await resp.json();
                        
                        if (json.success) {
                            var preview = json.preview || json.transcript.substring(0, 500);
                            infoDiv.innerHTML = '<strong>' + (rec.title || 'Untitled') + '</strong><br>' +
                                'Date: ' + (rec.date || 'Unknown') + '<br>' +
                                'Duration: ' + durationMins + ' minutes<br>' +
                                'Participants: ' + (rec.participants ? rec.participants.join(', ') : 'Unknown') +
                                '<br><br><strong>Transcript Preview:</strong><br>' +
                                '<pre style="max-height:150px;overflow:auto;font-size:11px;background:#f8f9fa;padding:8px;border-radius:4px;white-space:pre-wrap;">' + 
                                preview.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre>';
                            status.className = 'fathom-status success';
                            status.textContent = 'Transcript loaded. Ready to grade.';
                        } else {
                            infoDiv.innerHTML += '<br><span style="color:#dc3545;">Error loading preview: ' + json.error + '</span>';
                        }
                    } catch(err) {
                        infoDiv.innerHTML += '<br><span style="color:#dc3545;">Error: ' + err.message + '</span>';
                    }
                }
            } else {
                infoDiv.style.display = 'none';
            }
        }
        
        document.getElementById('gradeForm').onsubmit = async function(e) {
            e.preventDefault();
            var result = document.getElementById('result');
            var report = document.getElementById('report');
            var loading = document.getElementById('loading');
            var loadingText = document.getElementById('loadingText');
            var btn = document.getElementById('submitBtn');
            
            result.style.display = 'none';
            report.style.display = 'none';
            loading.style.display = 'block';
            btn.disabled = true;
            
            var data = {
                student_name: document.getElementById('studentName').value,
                tutor_name: document.getElementById('tutorName').value,
                tutor_email: document.getElementById('tutorEmail').value,
                session_date: document.getElementById('sessionDate').value
            };
            
            if (currentMode === 'paste') {
                var transcript = document.getElementById('transcript').value;
                if (!transcript.trim()) {
                    result.className = 'result error';
                    result.innerHTML = 'Error: Please paste a transcript';
                    result.style.display = 'block';
                    loading.style.display = 'none';
                    btn.disabled = false;
                    return;
                }
                data.transcript = transcript;
                loadingText.textContent = 'Analyzing transcript and generating comprehensive report...';
            } else {
                var recordingId = document.getElementById('recordingId').value;
                if (!recordingId) {
                    result.className = 'result error';
                    result.innerHTML = 'Error: Please select a recording from Fathom';
                    result.style.display = 'block';
                    loading.style.display = 'none';
                    btn.disabled = false;
                    return;
                }
                data.recording_id = recordingId;
                loadingText.textContent = 'Fetching transcript from Fathom and generating comprehensive report...';
            }
            
            try {
                var resp = await fetch('/api/grade', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                var json = await resp.json();
                
                if (json.success) {
                    result.className = 'result success';
                    result.innerHTML = '<strong>Grading Complete!</strong><br>Score: ' + json.raw_total + '/135 — <em>' + json.overall_rating + '</em> (A: ' + json.a_total + '/50 | B: ' + json.b_total + '/50 | C: ' + json.c_total + '/20 | D: ' + json.d_total + '/15)<br>Email sent: ' + (json.email_sent ? 'Yes' : 'No - check email config');
                    report.textContent = json.report;
                    report.style.display = 'block';
                } else {
                    result.className = 'result error';
                    result.innerHTML = 'Error: ' + json.error;
                }
            } catch(err) {
                result.className = 'result error';
                result.innerHTML = 'Error: ' + err.message;
            }
            loading.style.display = 'none';
            result.style.display = 'block';
            btn.disabled = false;
        };
    </script>
</body>
</html>"""


@app.route('/')
def index():
    return Response(get_html(), mimetype='text/html')


@app.route('/api/fathom-status')
def fathom_status():
    """Check if Fathom API is configured."""
    client = FathomClient()
    return jsonify({
        'configured': client.is_configured(),
        'message': 'Fathom API key is configured' if client.is_configured() else 'FATHOM_API_KEY environment variable not set'
    })


@app.route('/api/list-recordings')
def list_recordings():
    """Fetch list of recordings from Fathom."""
    client = FathomClient()
    
    if not client.is_configured():
        return jsonify({
            'success': False,
            'error': 'Fathom API key not configured. Please set FATHOM_API_KEY environment variable.'
        }), 400
    
    result = client.get_recordings(limit=50)
    return jsonify(result)


@app.route('/api/get-transcript')
def get_transcript():
    """Fetch and format transcript for a specific recording from Fathom."""
    recording_id = request.args.get('recording_id', '')
    
    if not recording_id:
        return jsonify({
            'success': False,
            'error': 'recording_id query parameter is required'
        }), 400
    
    client = FathomClient()
    
    if not client.is_configured():
        return jsonify({
            'success': False,
            'error': 'Fathom API key not configured. Please set FATHOM_API_KEY environment variable.'
        }), 400
    
    result = client.get_transcript(recording_id)
    
    if not result.get('success'):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to fetch transcript')
        }), 400
    
    return jsonify({
        'success': True,
        'transcript': result.get('transcript', ''),
        'recording_title': result.get('recording_title', ''),
        'preview': result.get('transcript', '')[:500] + '...' if len(result.get('transcript', '')) > 500 else result.get('transcript', '')
    })


@app.route('/api/grade', methods=['POST'])
def grade_session():
    try:
        data = request.get_json()
        
        # Check for required fields (except transcript which can come from Fathom)
        required_fields = ['student_name', 'tutor_name', 'tutor_email', 'session_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': 'Missing: ' + field}), 400
        
        # Get transcript either from direct input or from Fathom
        transcript = data.get('transcript', '')
        recording_id = data.get('recording_id', '')
        
        if not transcript and not recording_id:
            return jsonify({
                'success': False,
                'error': 'Either transcript or recording_id is required'
            }), 400
        
        # If recording_id is provided, fetch transcript from Fathom
        if recording_id and not transcript:
            client = FathomClient()
            
            if not client.is_configured():
                return jsonify({
                    'success': False,
                    'error': 'Fathom API key not configured. Cannot fetch transcript.'
                }), 400
            
            result = client.get_transcript(recording_id)
            
            if not result.get('success'):
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch transcript from Fathom: ' + result.get('error', 'Unknown error')
                }), 400
            
            transcript = result.get('transcript', '')
            
            if not transcript:
                return jsonify({
                    'success': False,
                    'error': 'Retrieved transcript from Fathom is empty'
                }), 400
        
        grader = SessionGrader(
            transcript=transcript,
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

        # Send grading report to all four directors
        subject = 'Session Grading Report - {} (Tutor: {})'.format(
            data['student_name'], data['tutor_name'])
        email_sent = send_email(DIRECTOR_EMAILS, subject, report)

        return jsonify({
            'success': True,
            'scores': findings['scores'],
            'a_total': findings['a_total'],
            'b_total': findings['b_total'],
            'c_total': findings['c_total'],
            'd_total': findings['d_total'],
            'raw_total': findings['raw_total'],
            'overall_rating': findings['overall_rating'],
            'director_email': DIRECTOR_EMAIL,
            'email_sent': email_sent,
            'report': report,
            'transcript_source': 'fathom' if recording_id else 'manual'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.1', 'fathom_configured': bool(FATHOM_API_KEY)})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print("Starting JW Session Grader on port " + str(port))
    print("Open http://localhost:{} in your browser".format(port))
    app.run(host='0.0.0.0', port=port, debug=True)
