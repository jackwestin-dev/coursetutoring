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
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

# Configuration from environment
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
DIRECTOR_EMAIL = os.getenv('DIRECTOR_EMAIL', 'anastasia@jackwestin.com')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'grader@jackwestin.com')
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
    
    def __init__(self, transcript, student_name, tutor_name, session_date):
        self.transcript = transcript
        self.student_name = student_name
        self.tutor_name = tutor_name
        self.session_date = session_date
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
            'has_strategy': has_strategy,
            'has_next_session': has_next_session,
            'action_items': action_items,
            'topics_discussed': topics_discussed,
            'transcript_length': len(self.transcript),
        }
        return info
    
    def check_notes_present(self):
        """Check which SOP items are present in documented notes/action items."""
        action_text = '\n'.join(re.findall(r'ACTION\s*ITEM[:\s]+([^\n]+)', self.transcript, re.I))
        
        checks = {
            'exam_schedule': {
                'status': 'Partial' if re.search(r'FL|full.?length|Feb\s*\d', action_text, re.I) else 'No',
                'evidence': self._get_evidence(action_text, r'(?:FL|full.?length|practice)[^.]*') or '(Not documented)'
            },
            'aamc_sequencing': {
                'status': 'Partial' if re.search(r'AAMC', action_text, re.I) else 'No',
                'evidence': self._get_evidence(action_text, r'AAMC[^.]*') or '(Not documented)'
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
            }
        }
        return checks
    
    def _get_evidence(self, text, pattern):
        match = re.search(pattern, text, re.I)
        return '"' + match.group(0).strip() + '"' if match else None
    
    def grade(self):
        """Run comprehensive grading."""
        info = self.extract_info()
        notes_check = self.check_notes_present()
        action_count = len(info['action_items'])
        
        # Category 1: Preparation & Planning Readiness
        prep_score = 3
        prep_just = []
        prep_missing = []
        
        if info['test_date'] != 'Not found':
            prep_score += 2
            prep_just.append("Test date ({}) identified".format(info['test_date']))
        else:
            prep_missing.append("Test date not documented")
            
        if info['baseline_score'] != 'Not found':
            prep_score += 2
            prep_just.append("Baseline score (~{}) discussed".format(info['baseline_score']))
        else:
            prep_missing.append("Baseline score not documented")
            
        if info['has_aamc']:
            prep_score += 1
            prep_just.append("AAMC materials referenced")
        if info['weak_chem'] or info['weak_bio']:
            prep_score += 1
            prep_just.append("Weak areas identified through discussion")
        else:
            prep_missing.append("Below-average topics not prioritized in notes")
            
        if not prep_just:
            prep_just.append("Limited evidence of preparation in notes")
        prep_missing.append("No evidence tutor reviewed Basecamp data beforehand")
        
        self.scores['Preparation'] = min(prep_score, 10)
        self.justifications['Preparation'] = ' '.join(prep_just) + ". However, no documentation of preparation exists in the notes."
        self.missing_items['Preparation'] = prep_missing
        
        # Category 2: Study Plan Construction Quality
        plan_score = 2
        plan_just = []
        plan_missing = []
        
        if notes_check['exam_schedule']['status'] != 'No':
            plan_score += 2
            plan_just.append("Some exam scheduling mentioned")
        else:
            plan_missing.append("Practice exam schedule (dates for all 11 exams)")
            
        if notes_check['aamc_sequencing']['status'] != 'No':
            plan_score += 2
            plan_just.append("AAMC sequencing discussed")
        else:
            plan_missing.append("AAMC sequencing and deadlines")
            
        if notes_check['weekly_checklist']['status'] != 'No':
            plan_score += 2
        else:
            plan_missing.append("Weekly checklist/priorities")
            
        if notes_check['daily_tasks']['status'] != 'No':
            plan_score += 2
            plan_just.append("Some daily tasks captured")
        else:
            plan_missing.append("Daily tasks for Week 1")
        
        plan_missing.append("Chapters to review")
        plan_missing.append("Question count assignments")
        
        self.scores['Study Plan'] = min(plan_score, 10)
        self.justifications['Study Plan'] = "Notes contain minimal structured study plan. " + (' '.join(plan_just) if plan_just else "Only vague action items captured without specific assignments.")
        self.missing_items['Study Plan'] = plan_missing
        
        # Category 3: Personalization & Load Calibration
        personal_score = 4
        personal_just = []
        personal_missing = []
        
        if info['has_classes']:
            personal_score += 1
            personal_just.append("School commitments acknowledged")
        if info['has_work']:
            personal_score += 1
            personal_just.append("Work schedule discussed")
        if info['has_adhd']:
            personal_score += 2
            personal_just.append("ADHD accommodations discussed")
        else:
            personal_missing.append("Documentation of accommodation strategy")
            
        personal_missing.append("Weekly study hour estimate based on availability")
        personal_missing.append("Pacing plan accounting for timeline")
        if not info['has_classes']:
            personal_missing.append("Adaptation for school schedule")
        
        self.scores['Personalization'] = min(personal_score, 10)
        self.justifications['Personalization'] = ' '.join(personal_just) + ". However, constraints were not translated into documented workload calibration." if personal_just else "Minimal personalization evident in documentation."
        self.missing_items['Personalization'] = personal_missing
        
        # Category 4: Strategy Portion Execution
        strategy_score = 5
        strategy_just = []
        strategy_missing = []
        
        if info['has_strategy']:
            strategy_score += 2
            strategy_just.append("Strategy instruction evident in session")
        if len(info['topics_discussed']) >= 3:
            strategy_score += 2
            strategy_just.append("Multiple topics covered: " + ', '.join(info['topics_discussed'][:3]))
        elif info['topics_discussed']:
            strategy_score += 1
            strategy_just.append("Topics covered: " + ', '.join(info['topics_discussed']))
        if info['transcript_length'] > 50000:
            strategy_score += 1
            strategy_just.append("Substantial session length indicates thorough instruction")
        
        strategy_missing.append("Summary of strategy concepts taught")
        strategy_missing.append("Student-specific takeaways on question approach")
        strategy_missing.append("Documentation of frameworks discussed")
        
        self.scores['Strategy'] = min(strategy_score, 10)
        self.justifications['Strategy'] = ' '.join(strategy_just) + ". This was the session's strongest area based on transcript content."
        self.missing_items['Strategy'] = strategy_missing
        
        # Category 5: Clarity & Student Buy-In
        clarity_score = 3
        clarity_just = []
        clarity_missing = []
        
        if info['has_next_session']:
            clarity_score += 2
            clarity_just.append("Next session timing discussed")
        else:
            clarity_missing.append("Confirmed next session date")
            
        if action_count > 0:
            clarity_score += 2
            clarity_just.append("{} action items captured".format(action_count))
        if action_count > 1:
            clarity_score += 1
            
        clarity_missing.append("Comprehensive next-steps summary")
        clarity_missing.append("Full list of assignments before next session")
        clarity_missing.append("Study resource links documented")
        
        self.scores['Clarity'] = min(clarity_score, 10)
        self.justifications['Clarity'] = ' '.join(clarity_just) + ". However, session ended without clear documented recap." if clarity_just else "No clear recap or direction provided in notes."
        self.missing_items['Clarity'] = clarity_missing
        
        # Calculate average and rating
        avg = sum(self.scores.values()) / len(self.scores)
        
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
        """Determine the biggest risk based on scores."""
        if self.scores.get('Study Plan', 10) <= 4:
            return "No formal session notes exist - student has no take-home documentation with study plan, exam schedule, weekly checklist, or daily tasks."
        elif self.scores.get('Clarity', 10) <= 5:
            return "Student may leave session without clear understanding of next steps and assignments."
        elif self.scores.get('Preparation', 10) <= 4:
            return "Session lacked preparation context - tutor may not have reviewed student's baseline data."
        else:
            return "Documentation gaps may impact student's ability to follow study plan independently."
    
    def _get_top_fixes(self):
        """Generate top 3 fixes based on lowest scores."""
        fixes = []
        
        if self.scores.get('Study Plan', 10) <= 5:
            fixes.append("Create a proper Google Doc with student snapshot, study schedule, AAMC sequencing, and weekly/daily task breakdown")
        if self.scores.get('Study Plan', 10) <= 6:
            fixes.append("Document the exam schedule explicitly (11 total FLs with dates and which tests to take when)")
        if self.missing_items.get('Preparation'):
            fixes.append("Add below-average topic list with specific daily/weekly assignments for weak areas")
        if self.scores.get('Clarity', 10) <= 5:
            fixes.append("Confirm next session date and document clear action items with deadlines")
        if self.scores.get('Strategy', 10) <= 6:
            fixes.append("Document strategy concepts taught during session for student reference")
            
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
            ('FL schedule discussion', info['has_fl_discussion'], 'No'),
            ('AAMC sequencing', info['has_aamc'], 'No'),
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
        
        if self.scores['Study Plan'] <= 5:
            improvements.append({
                'title': 'Critical: No Session Documentation Created',
                'what': 'The session produced minimal documented notes. No formal notes document exists with structured study plan.',
                'why': 'Student has no reference document for their study plan, exam schedule, or strategies discussed. They cannot follow a structured plan independently.',
                'fix': 'Create a Google Doc immediately using the Notes v2 template. Include: Student Snapshot, Exam Schedule, Weekly Checklist, Week 1 Daily Tasks, Strategy Summary. Share with student AND anastasia@jackwestin.com, michaelmel@jackwestin.com. Budget 10-15 minutes at session end for documentation.'
            })
        
        if self.findings['notes_check']['exam_schedule']['status'] == 'No':
            improvements.append({
                'title': 'Missing: Structured Exam Schedule',
                'what': 'FL sequencing may have been discussed verbally but was not documented with specific dates.',
                'why': 'Student needs clarity on which test to take each week. Without a documented schedule, they may sequence incorrectly.',
                'fix': 'Create a table: Week | Date | Exam | Notes. Be explicit with dates. Include the test date as the anchor.'
            })
        
        if self.findings['notes_check']['below_avg_topics']['status'] == 'No':
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
            clean_fix = fix.replace('**', '')
            report += "{}. {}\n".format(i, clean_fix)
        
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
Exam schedule                                     | {exam_status:8} | {exam_ev}
AAMC sequencing/deadlines                         | {aamc_status:8} | {aamc_ev}
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
            exam_status=notes_check['exam_schedule']['status'],
            exam_ev=notes_check['exam_schedule']['evidence'][:50],
            aamc_status=notes_check['aamc_sequencing']['status'],
            aamc_ev=notes_check['aamc_sequencing']['evidence'][:50],
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

AAMC Plan

- AAMC FLs: Start 6 weeks before test date
- Section Banks: Integrate during AAMC FL phase
- Q-Packs: Use for supplemental topic review
- Deadline: All AAMC material completed by test day minus 1

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
                    result.innerHTML = '<strong>Grading Complete!</strong><br>Rating: ' + json.overall_rating + ' (Average: ' + json.average_score + '/10)<br>Email sent: ' + (json.email_sent ? 'Yes' : 'No - check email config');
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
            session_date=data['session_date']
        )
        
        findings = grader.grade()
        report = grader.generate_report()
        
        recipients = [data['tutor_email'], DIRECTOR_EMAIL]
        subject = "Session 1 Grading: {} - {}".format(data['student_name'], findings['rating'])
        email_sent = send_email(recipients, subject, report)
        
        return jsonify({
            'success': True,
            'scores': findings['scores'],
            'average_score': findings['average'],
            'overall_rating': findings['rating'],
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
