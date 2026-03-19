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
        """Check which SOP items are present in documented notes/action items."""
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
                # Most/all exam dates are the March 5th placeholder — not actually scheduled
                fl_status = 'No'
                fl_evidence = 'Exam dates use default March 5th placeholder — not actually scheduled by tutor'
            elif march5_count > 0 and total_dates > march5_count:
                # Some exams have real dates, some have placeholder
                fl_status = 'Partial'
                fl_evidence = 'Some exams scheduled but {} of {} dates are the March 5th default placeholder'.format(march5_count, total_dates)
            else:
                fl_status = 'Partial'
                fl_evidence = self._get_evidence(action_text, r'(?:FL|full.?length|practice\s*exam|JW\s*FL)[^.]*') or '(FL exams referenced)'
        else:
            fl_status = 'No'
            fl_evidence = '(Not documented)'

        checks = {
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
            }
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
        """Run comprehensive grading using 150-point architecture: SOP 60, Notes 30, Coaching 60."""
        if self.course_type == 'cars':
            return self._grade_cars()
        info = self.extract_info()
        notes_check = self.check_notes_present()
        probing = self._detect_probing_questions()

        # Initialize new score dict (Section 2: SOP 60, Section 3: Notes 30, Section 4: Coaching 60)
        self.scores = {
            'sop_fl_exam_schedule': 0, 'sop_aamc_question_packs': 0, 'sop_below_avg_topics': 0,
            'sop_weekly_checklist': 0, 'sop_daily_tasks': 0, 'sop_strategy_notes': 0,
            'sop_next_session': 0, 'sop_major_takeaways': 0,
            'notes_preparation': 0, 'notes_study_plan': 0, 'notes_personalization': 0,
            'coaching_strategy': 0, 'coaching_probing': 0,
        }
        self.justifications = {}
        self.missing_items = {}

        # --- Section 2: SOP Compliance (60 pts) ---
        # SOP verification inputs act as third source of truth (YES=full, PARTIAL=50%, NO=0 unless overridden)
        # 1. Full-Length Exam schedule: 12 full, 6 partial, 0 missing
        fl_status = notes_check['fl_exam_schedule']['status']
        if fl_status == 'Yes' or self.sop_full_length_exams == 'yes':
            self.scores['sop_fl_exam_schedule'] = 12
        elif fl_status == 'Partial' or self.sop_full_length_exams == 'partial':
            self.scores['sop_fl_exam_schedule'] = 6
        # 2. AAMC Question Packs/Resources: 8 full, 4 partial, 0 missing (conditional)
        aamc_status = notes_check['aamc_question_packs']['status']
        if aamc_status == 'Yes' or self.sop_question_packs == 'yes':
            self.scores['sop_aamc_question_packs'] = 8
        elif aamc_status == 'Partial' or self.sop_question_packs == 'partial':
            self.scores['sop_aamc_question_packs'] = 4
        # 3. Below-average topics: 10 full, 5 partial, 0
        if notes_check['below_avg_topics']['status'] == 'Yes':
            self.scores['sop_below_avg_topics'] = 10
        elif notes_check['below_avg_topics']['status'] == 'Partial':
            self.scores['sop_below_avg_topics'] = 5
        # 4. Weekly checklist: 8 or 0
        self.scores['sop_weekly_checklist'] = 8 if notes_check['weekly_checklist']['status'] in ('Yes', 'Partial') else 0
        # 5. Daily tasks: 8 full, 4 partial, 0
        if notes_check['daily_tasks']['status'] == 'Yes':
            self.scores['sop_daily_tasks'] = 8
        elif notes_check['daily_tasks']['status'] == 'Partial':
            self.scores['sop_daily_tasks'] = 4
        # 6. Strategy notes: 7 full, 3-4 brief, 0
        if notes_check['strategy_notes']['status'] == 'Yes':
            self.scores['sop_strategy_notes'] = 7
        elif notes_check['strategy_notes']['status'] == 'Partial':
            self.scores['sop_strategy_notes'] = 4
        # 7. Next session: 4 or 0
        self.scores['sop_next_session'] = 4 if notes_check['next_session']['status'] in ('Yes', 'Partial') else 0
        # 8. Major takeaways (from transcript, binary)
        self.scores['sop_major_takeaways'] = 3 if notes_check['sop_major_takeaways']['status'] == 'Yes' else 0

        # --- Section 3: Notes Quality (30 pts) ---
        # A. Preparation & Planning Readiness 0-10
        prep_pts = 0
        if info['test_date'] != 'Not found':
            prep_pts += 3
        if info['baseline_score'] != 'Not found':
            prep_pts += 3
        if info['has_aamc']:
            prep_pts += 2
        if info['weak_chem'] or info['weak_bio']:
            prep_pts += 3
        self.scores['notes_preparation'] = min(prep_pts, 15)
        self.justifications['notes_preparation'] = "Preparation evidence: test date, baseline, AAMC materials ref, weak areas."
        self.missing_items['notes_preparation'] = [x for x in ["Test date", "Baseline score", "Below-average topics"] if (x == "Test date" and info['test_date'] == 'Not found') or (x == "Baseline score" and info['baseline_score'] == 'Not found') or (x == "Below-average topics" and not (info['weak_chem'] or info['weak_bio']))]

        # B. Study Plan Construction 0-13 — incorporates SOP verification as third source
        plan_pts = 0
        fl_plan_ok = notes_check['fl_exam_schedule']['status'] != 'No' or self.sop_full_length_exams in ('yes', 'partial')
        aamc_plan_ok = notes_check['aamc_question_packs']['status'] != 'No' or self.sop_question_packs in ('yes', 'partial')
        if fl_plan_ok:
            plan_pts += 5
        if aamc_plan_ok:
            plan_pts += 5
        if notes_check['weekly_checklist']['status'] != 'No' or self.sop_study_schedule in ('yes', 'partial'):
            plan_pts += 4
        if notes_check['daily_tasks']['status'] == 'Yes':
            plan_pts += 6
        elif notes_check['daily_tasks']['status'] == 'Partial':
            plan_pts += 3
        self.scores['notes_study_plan'] = min(plan_pts, 20)
        self.justifications['notes_study_plan'] = "Study plan structure: FL exam schedule, AAMC question packs, weekly/daily tasks (includes SOP verification inputs)."
        self.missing_items['notes_study_plan'] = [k for k, v in [('FL exam schedule', {'status': 'No' if not fl_plan_ok else 'Yes'}), ('AAMC question packs', {'status': 'No' if not aamc_plan_ok else 'Yes'}), ('Weekly checklist', notes_check['weekly_checklist']), ('Daily tasks Week 1', notes_check['daily_tasks'])] if v['status'] == 'No']

        # C. Personalization & Load 0-7
        personal_pts = 0
        if info['has_classes'] or info['has_work']:
            personal_pts += 3
        if info['has_adhd']:
            personal_pts += 2
        if notes_check['daily_tasks']['status'] != 'No' or info['has_classes']:
            personal_pts += 2
        self.scores['notes_personalization'] = min(personal_pts, 7)
        self.justifications['notes_personalization'] = "Personalization: availability, constraints, workload calibration."
        self.missing_items['notes_personalization'] = ["Weekly study hours", "Pacing for timeline"] if not (info['has_classes'] or info['has_work']) else []

        # --- Section 4: Transcript Coaching Quality (60 pts) ---
        # D. Strategy Portion Execution 0-33 (cap 24 if only CARS or only science)
        has_cars = bool(re.search(r'(?:mapping|main idea|CARS passage|argument|author.*opinion|reference to authority|contrast word)', self.transcript, re.I))
        has_science = bool(re.search(r'(?:science passage|experimental passage|reference.*table|unit analysis|figure|graph|TAQT|buzz\s*word|discrete)', self.transcript, re.I))
        both_covered = has_cars and has_science
        strategy_raw = 0
        if info['has_strategy']:
            strategy_raw += 11
        if len(info['topics_discussed']) >= 3:
            strategy_raw += 11
        elif info['topics_discussed']:
            strategy_raw += 7
        if info['transcript_length'] > 40000:
            strategy_raw += 5
        strategy_raw = min(strategy_raw, 33)
        self.scores['coaching_strategy'] = min(strategy_raw, 24) if not both_covered else strategy_raw
        self.justifications['coaching_strategy'] = "Strategy coverage: CARS and science both covered." if both_covered else "Strategy coverage: only one of CARS or science covered; cap applied."
        self.missing_items['coaching_strategy'] = [] if both_covered else ["Cover both CARS and science strategy for full points."]

        # E. Student-Led Learning & Probing Questions 0-27
        density = probing['probing_density']
        count = probing['positive_count']
        if count >= 8 or density >= 2.0:
            probing_pts = 24
        elif count >= 5 or density >= 1.2:
            probing_pts = 19
        elif count >= 3 or density >= 0.6:
            probing_pts = 13
        elif count >= 1:
            probing_pts = 7
        else:
            probing_pts = 2
        self.scores['coaching_probing'] = min(probing_pts, 27)
        self.justifications['coaching_probing'] = "Probing questions and student-led learning: {} signals in transcript.".format(count)
        self.missing_items['coaching_probing'] = ["Use more probing questions; have student explain back."] if probing_pts < 10 else []

        # --- Totals and rating ---
        sop_total = sum(self.scores[k] for k in self.scores if k.startswith('sop_'))
        notes_total = sum(self.scores[k] for k in self.scores if k.startswith('notes_'))
        coaching_total = sum(self.scores[k] for k in self.scores if k.startswith('coaching_'))
        raw_total = sop_total + notes_total + coaching_total
        scaled_score = round((raw_total / 150.0) * 100)
        if scaled_score >= 90:
            rating = 'Exceeds'
        elif scaled_score >= 75:
            rating = 'Meets'
        elif scaled_score >= 60:
            rating = 'Coach'
        else:
            rating = 'Remediate'

        self.findings = {
            'info': info,
            'notes_check': notes_check,
            'scores': self.scores,
            'sop_total': sop_total,
            'notes_total': notes_total,
            'coaching_total': coaching_total,
            'raw_total': raw_total,
            'scaled_score': scaled_score,
            'rating': rating
        }
        return self.findings
    
    def _get_biggest_risk(self):
        """Determine the biggest risk based on scores."""
        if self.findings.get('sop_total', 0) < 35:
            return "SOP compliance is low — student has insufficient take-home documentation (FL exam schedule, AAMC question pack scheduling, weekly/daily tasks, or major takeaways closing)."
        if self.scores.get('sop_major_takeaways', 0) == 0:
            return "Required closing missing: tutor did not ask 'What were your major takeaways?' in the final portion of the session."
        if self.findings.get('notes_total', 0) < 25:
            return "Notes quality is weak — preparation, study plan, or personalization not adequately documented."
        if self.findings.get('coaching_total', 0) < 25:
            return "Coaching quality gaps — strategy coverage or probing questions need improvement."
        return "Documentation and coaching gaps may impact student's ability to follow the study plan independently."
    
    def _get_top_fixes(self):
        """Generate top 3 fixes based on lowest scores and missing items."""
        fixes = []
        if self.scores.get('sop_fl_exam_schedule', 0) < 12:
            fixes.append("Document FL exam schedule with all 10 dates (JW FL 1-6 + AAMC exams) in notes")
        if self.scores.get('sop_aamc_question_packs', 0) < 8:
            fixes.append("Schedule AAMC question packs/resources (if student has them) with deadlines in the study plan")
        if self.scores.get('sop_major_takeaways', 0) == 0:
            fixes.append("Required closing: Ask 'What were your major takeaways?' at session end (all 515+, Intensive, CARS sessions)")
        if self.scores.get('sop_next_session', 0) == 0:
            fixes.append("Confirm and document next session date in notes")
        if self.scores.get('notes_study_plan', 0) < 14:
            fixes.append("Create or complete study plan with weekly checklist and Week 1 daily tasks")
        if self.scores.get('coaching_probing', 0) < 10:
            fixes.append("Use more probing questions; have student explain back rather than lecturing")
        return fixes[:3]
    
    def _generate_gap_analysis(self):
        """Generate transcript vs notes gap analysis."""
        info = self.findings['info']
        gaps = []
        
        gap_items = [
            ('Test date: ' + info['test_date'], info['test_date'] != 'Not found', 'No'),
            ('Baseline score: ~' + info['baseline_score'], info['baseline_score'] != 'Not found', 'No'),
            ('Target score: ' + info['target_score'], info['target_score'] != 'Not found', 'No'),
            ('Student constraints (classes, accommodations)', info['has_classes'] or info['has_adhd'], 'No'),
            ('Weak areas identified', info['weak_chem'] or info['weak_bio'], 'No'),
            ('Strong areas (CARS, Psych/Soc)', info['strong_cars'] or info['strong_psych'], 'No'),
            ('FL exam schedule (10 exams: JW FL + AAMC)', info['has_fl_discussion'], 'No'),
            ('AAMC question packs/resources scheduling', info.get('has_aamc_qpacks', info['has_aamc']), 'No'),
        ]
        
        for topic in info['topics_discussed']:
            gap_items.append((topic + ' strategy', True, 'Partial'))
            
        gap_items.append(('Next session timing', info['has_next_session'], 'No'))
        
        return gap_items
    
    def _generate_tutor_feedback(self):
        """Generate detailed tutor feedback."""
        info = self.findings['info']
        
        # What went well
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
            positives.append(("Multi-Topic Coverage", "Covered {} distinct topic areas: {}".format(len(info['topics_discussed']), ', '.join(info['topics_discussed']))))
        
        if not positives:
            positives.append(("Session Completed", "Session was held and covered material with the student."))
        
        # Areas for improvement
        improvements = []
        sop_total = self.findings.get('sop_total', 0)
        notes_check = self.findings['notes_check']
        
        if sop_total < 40:
            improvements.append({
                'title': 'Critical: SOP Documentation Gaps',
                'what': 'Multiple required SOP items are missing or partial (FL exam schedule, AAMC question pack scheduling, weekly/daily tasks, or major takeaways closing).',
                'why': 'Student needs a complete take-home document and a clear session close. Without it, they cannot follow the plan independently.',
                'fix': 'Create a Google Doc with Student Snapshot, FL Exam Schedule (10 exams: JW FL 1-6 + AAMC exams), AAMC Question Pack scheduling (if student has them), Weekly Checklist, Week 1 Daily Tasks, Strategy Summary. End every session by asking: "What were your major takeaways?"'
            })
        
        if notes_check['fl_exam_schedule']['status'] == 'No':
            improvements.append({
                'title': 'Missing: Structured FL Exam Schedule',
                'what': 'FL sequencing may have been discussed verbally but was not documented with specific dates.',
                'why': 'Student needs clarity on which test to take each week. Without a documented schedule, they may sequence incorrectly.',
                'fix': 'Create a table: Week | Date | Exam | Notes. Be explicit with dates. Include the test date as the anchor.'
            })
        
        if notes_check['below_avg_topics']['status'] == 'No':
            improvements.append({
                'title': 'Missing: Below-Average Topic Prioritization',
                'what': 'Weak areas may have been identified through discussion but no prioritized topic list was created in notes.',
                'why': 'Student needs specific topics to focus on. Without this list, they may study inefficiently.',
                'fix': 'Create a "Priority Topics" section organized by MCAT section. Exclude topics covered by live course. Rank by importance.'
            })
        
        if self.scores.get('sop_next_session', 0) == 0:
            improvements.append({
                'title': 'Incomplete: Next Session Planning',
                'what': 'No specific next session date was confirmed or documented.',
                'why': 'Without a confirmed date, follow-up may slip. Session 1 momentum is critical.',
                'fix': 'Always confirm a specific date before ending Session 1. Document it in notes with planned focus areas. Include "Student to bring: [items]".'
            })
        
        if notes_check.get('sop_major_takeaways', {}).get('status') == 'No':
            improvements.append({
                'title': 'Required: Major Takeaways Closing',
                'what': 'Tutor did not ask the student about their major takeaways in the final portion of the session.',
                'why': 'This closing is required for all 515+, Intensive, and CARS sessions to reinforce learning.',
                'fix': 'In the last 5–10 minutes, ask: "What were your major takeaways from today?" or similar. Document in notes if relevant.'
            })
        
        return positives, improvements
    
    def generate_report(self):
        """Generate the full comprehensive grading report in clean format."""
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
            clean_fix = fix.replace('**', '')
            report += "{}. {}\n".format(i, clean_fix)
        
        report += """
{sep}

SECTION 2: SOP COMPLIANCE CHECKLIST (60 pts)

SOP Item                                          | Score | Max | Evidence
--------------------------------------------------|-------|-----|---------
Full-Length Exam schedule (10 FLs)                | {sop_exam:2} | 12 | {exam_ev}
AAMC Question Packs/Resources scheduling          | {sop_aamc:2} |  8 | {aamc_ev}
Below-average topic review                        | {sop_topics:2} | 10 | {topics_ev}
Weekly checklist present                          | {sop_weekly:2} |  8 | {weekly_ev}
Daily tasks for Week 1 documented                 | {sop_daily:2} |  8 | {daily_ev}
Strategy portion notes documented                 | {sop_strat:2} |  7 | {strat_ev}
Next session tentatively scheduled                | {sop_next:2} |  4 | {next_ev}
Major Takeaways closing (transcript)              | {sop_takeaways:2} |  3 | {takeaways_ev}
--------------------------------------------------|-------|-----|---------
SOP Subtotal                                      | {sop_total:2} | 60 |

{sep}

SECTION 3: NOTES QUALITY (30 pts)

A. Preparation & Planning Readiness               | {notes_prep:2} | 10
Justification: {notes_prep_just}
Missing: {notes_prep_missing}

B. Study Plan Construction Quality                | {notes_plan:2} | 13
Justification: {notes_plan_just}
Missing: {notes_plan_missing}

C. Personalization & Load Calibration             | {notes_personal:2} |  7
Justification: {notes_personal_just}
Missing: {notes_personal_missing}
Notes Subtotal                                    | {notes_total:2} | 30

{sep}

SECTION 4: TRANSCRIPT COACHING QUALITY (60 pts)

D. Strategy Portion Execution                     | {coach_strat:2} | 33
Justification: {coach_strat_just}
Missing: {coach_strat_missing}

E. Student-Led Learning & Probing Questions       | {coach_probing:2} | 27
Justification: {coach_probing_just}
Missing: {coach_probing_missing}
Coaching Subtotal                                 | {coaching_total:2} | 60

{sep}

SECTION 5: SOP EVIDENCE (NOTES-BASED)

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

SECTION 6: TRANSCRIPT VS. NOTES GAP ANALYSIS

What Was Discussed in Transcript (Should Have Been in Notes)

Topic Discussed                                           | In Notes?
----------------------------------------------------------|----------
""".format(
            sop_exam=self.scores['sop_fl_exam_schedule'],
            sop_aamc=self.scores['sop_aamc_question_packs'],
            sop_topics=self.scores['sop_below_avg_topics'],
            sop_weekly=self.scores['sop_weekly_checklist'],
            sop_daily=self.scores['sop_daily_tasks'],
            sop_strat=self.scores['sop_strategy_notes'],
            sop_next=self.scores['sop_next_session'],
            sop_takeaways=self.scores['sop_major_takeaways'],
            sop_total=f['sop_total'],
            notes_prep=self.scores['notes_preparation'],
            notes_prep_just=self.justifications.get('notes_preparation', ''),
            notes_prep_missing=', '.join(self.missing_items.get('notes_preparation', [])),
            notes_plan=self.scores['notes_study_plan'],
            notes_plan_just=self.justifications.get('notes_study_plan', ''),
            notes_plan_missing=', '.join(self.missing_items.get('notes_study_plan', [])),
            notes_personal=self.scores['notes_personalization'],
            notes_personal_just=self.justifications.get('notes_personalization', ''),
            notes_personal_missing=', '.join(self.missing_items.get('notes_personalization', [])),
            notes_total=f['notes_total'],
            coach_strat=self.scores['coaching_strategy'],
            coach_strat_just=self.justifications.get('coaching_strategy', ''),
            coach_strat_missing=', '.join(self.missing_items.get('coaching_strategy', [])),
            coach_probing=self.scores['coaching_probing'],
            coach_probing_just=self.justifications.get('coaching_probing', ''),
            coach_probing_missing=', '.join(self.missing_items.get('coaching_probing', [])),
            coaching_total=f['coaching_total'],
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

SECTION 7: RECOMMENDED NOTES REWRITE (NOTES V2)

Given that multiple critical SOP items are missing from notes, below is a recommended rewrite.

{sep}

{notes_v2}

{sep}

SECTION 8: TUTOR FEEDBACK

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

Section                              | Score  | Max
-------------------------------------|--------|-----
SOP Compliance Checklist             | {sop_total:2}     | 60
  — Full-Length Exam schedule        | {sop_exam:2}      | 12
  — AAMC Question Packs/Resources   | {sop_aamc:2}      |  8
  — Below-average topics             | {sop_topics:2}      | 10
  — Weekly checklist                | {sop_weekly:2}      |  8
  — Daily tasks (Week 1)             | {sop_daily:2}      |  8
  — Strategy notes                   | {sop_strat:2}      |  7
  — Next session scheduled           | {sop_next:2}      |  4
  — Major takeaways closing          | {sop_takeaways:2}      |  3
Notes Quality                        | {notes_total:2}     | 30
  A. Preparation & Planning         | {notes_prep:2}     | 10
  B. Study Plan Construction         | {notes_plan:2}     | 13
  C. Personalization & Load          | {notes_personal:2}     |  7
Transcript Coaching Quality          | {coaching_total:2}     | 60
  D. Strategy Portion Execution      | {coach_strat:2}     | 33
  E. Student-Led / Probing Qs        | {coach_probing:2}     | 27
-------------------------------------|--------|-----
RAW TOTAL                            | {raw_total:3}    | 150
SCALED SCORE                         | {scaled_score:2}/100

Overall Rating: {rating}

Summary:
{summary}

Recommended Actions:
1. Tutor should immediately create and share a comprehensive Session 1 Google Doc (see Notes v2 above)
2. Confirm next session date in writing; close every session with "What were your major takeaways?"
3. Future sessions should include 5-10 minutes at end for documentation review with student

{sep}

Graded by: JW Session Notes Grader Agent
Grading Agent Version: 2.0 (150-point architecture)
Reference Documents: first_session_sop_agent.md, grading_first_session_agent.md, session_1_grading_agent.md
""".format(
            tutor=self.tutor_name.split()[0] if self.tutor_name else 'Tutor',
            sop_total=f['sop_total'],
            sop_exam=self.scores['sop_fl_exam_schedule'],
            sop_aamc=self.scores['sop_aamc_question_packs'],
            sop_topics=self.scores['sop_below_avg_topics'],
            sop_weekly=self.scores['sop_weekly_checklist'],
            sop_daily=self.scores['sop_daily_tasks'],
            sop_strat=self.scores['sop_strategy_notes'],
            sop_next=self.scores['sop_next_session'],
            sop_takeaways=self.scores['sop_major_takeaways'],
            notes_total=f['notes_total'],
            notes_prep=self.scores['notes_preparation'],
            notes_plan=self.scores['notes_study_plan'],
            notes_personal=self.scores['notes_personalization'],
            coaching_total=f['coaching_total'],
            coach_strat=self.scores['coaching_strategy'],
            coach_probing=self.scores['coaching_probing'],
            raw_total=f['raw_total'],
            scaled_score=f['scaled_score'],
            rating=f['rating'],
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
        scaled = self.findings.get('scaled_score', 0)
        if scaled >= 90:
            return "Excellent session with comprehensive documentation and strong coaching. All major SOP items are addressed and the student has clear direction."
        elif scaled >= 75:
            return "Good session with adequate documentation. Minor improvements recommended for completeness. Score bands: 90-100 Exceeds, 75-89 Meets, 60-74 Coach, below 60 Remediate."
        elif scaled >= 60:
            return "The tutoring session content appears solid based on transcript analysis. However, documentation or coaching gaps exist. Address SOP items (FL exam schedule, AAMC question pack scheduling, major takeaways closing) and notes quality to improve the scaled score."
        else:
            return "Significant documentation or coaching gaps identified. The session requires immediate follow-up: create comprehensive session notes, confirm next session date, and close every session by asking 'What were your major takeaways?'"


    # ─── CARS Strategy Course grading (125-point rubric, Sessions 1-2) ────────

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
            a4 += 5  # auto-award S2 items
        else:
            if re.search(r'(?:hw\s*tracker|homework\s*tracker|timed\s*cars|cars\s*assignment)', combined):
                a4 += 3
            if re.search(r'(?:troubleshoot|test.?day|running\s*out\s*of\s*time|toolkit)', combined):
                a4 += 2
            a4 += 6  # auto-award S1 items

        sop_total = a1 + a2 + a3 + a4

        # ── B. Coaching Quality (45 pts) ──
        b1 = 0
        probing_patterns = [r'what do you think', r'why (?:is|do|would)', r'how would you',
                            r'can you explain', r'walk me through', r'tell me',
                            r'in your own words', r'what happens']
        probing_count = sum(len(re.findall(p, text)) for p in probing_patterns)
        if probing_count >= 5:
            b1 += 5
        elif probing_count >= 2:
            b1 += 3
        b1 += 5  # student talking — default full
        if not re.search(r'(?:let me (?:map|do) (?:it|this) for you|i\'ll map)', text):
            b1 += 5

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
        d += 3  # on time — assume yes
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
                    result.innerHTML = '<strong>Grading Complete!</strong><br>Score: ' + json.scaled_score + '/100 — <em>' + json.overall_rating + '</em><br>Raw: ' + json.raw_total + '/150 (SOP: ' + json.sop_total + '/60 | Notes: ' + json.notes_total + '/30 | Coaching: ' + json.coaching_total + '/60)<br>Email sent: ' + (json.email_sent ? 'Yes' : 'No - check email config');
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
            'sop_total': findings['sop_total'],
            'notes_total': findings['notes_total'],
            'coaching_total': findings['coaching_total'],
            'raw_total': findings['raw_total'],
            'overall_rating': findings['rating'],
            'director_email': DIRECTOR_EMAIL,
            'email_sent': email_sent,
            'report': report,
            'transcript_source': 'fathom' if recording_id else 'manual',
        }
        if grader.course_type == 'cars':
            response_data['max_total'] = findings['max_total']
            response_data['professionalism_total'] = findings.get('professionalism_total', 0)
        else:
            response_data['scaled_score'] = findings['scaled_score']

        return jsonify(response_data)
        
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
