# JW Session 1 Grading App

A web application that grades MCAT tutoring Session 1 transcripts and emails reports to tutors and directors.

## Features

- **Web Interface**: Drag-and-drop transcript upload
- **Automated Grading**: 5-category rubric scoring (1-10 scale)
- **Email Reports**: Sends formatted reports to tutor + director
- **SOP Compliance**: Checks against Session 1 requirements

## Quick Start

### 1. Install Dependencies

```bash
cd course_tutoring_app
pip install -r requirements.txt
```

### 2. Configure Email

```bash
cp .env.example .env
# Edit .env with your email credentials
```

**Gmail Setup:**
1. Enable 2-factor authentication on your Google account
2. Go to Google Account → Security → App Passwords
3. Generate an app password for "Mail"
4. Use that password in `.env`

### 3. Run Locally

```bash
python app.py
```

Open http://localhost:5000 in your browser.

---

## Deployment Options

### Option A: Railway (Recommended - Free Tier)

1. Push to GitHub
2. Go to [railway.app](https://railway.app)
3. Click "New Project" → "Deploy from GitHub repo"
4. Add environment variables in Railway dashboard
5. Deploy!

```bash
# Railway will auto-detect Python and use gunicorn
```

### Option B: Render

1. Push to GitHub
2. Go to [render.com](https://render.com)
3. Create new "Web Service"
4. Connect your repo
5. Set environment variables
6. Deploy

**render.yaml** (optional):
```yaml
services:
  - type: web
    name: jw-grader
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: SMTP_SERVER
        sync: false
      - key: SMTP_USER
        sync: false
      - key: SMTP_PASSWORD
        sync: false
      - key: DIRECTOR_EMAIL
        sync: false
```

### Option C: Docker

```bash
# Build
docker build -t jw-grader .

# Run
docker run -p 5000:5000 --env-file .env jw-grader
```

### Option D: Heroku

```bash
# Install Heroku CLI, then:
heroku create jw-session-grader
heroku config:set SMTP_SERVER=smtp.gmail.com
heroku config:set SMTP_PORT=587
heroku config:set SMTP_USER=your-email@gmail.com
heroku config:set SMTP_PASSWORD=your-app-password
heroku config:set DIRECTOR_EMAIL=anastasia@jackwestin.com

git push heroku main
```

---

## API Reference

### POST /api/grade

Grade a session transcript and send email reports.

**Request:**
```json
{
  "student_name": "Anji Herman",
  "tutor_name": "Ian Abrams",
  "tutor_email": "ian@jackwestin.com",
  "session_date": "2026-02-02",
  "transcript": "Full transcript text here..."
}
```

**Response:**
```json
{
  "success": true,
  "scores": {
    "Preparation": 7,
    "Study Plan": 4,
    "Personalization": 6,
    "Strategy": 8,
    "Clarity": 5
  },
  "average_score": 6.0,
  "overall_rating": "Needs Improvement",
  "director_email": "anastasia@jackwestin.com",
  "email_sent": true,
  "report": "# Session 1 Grading Report..."
}
```

### GET /api/health

Health check endpoint.

```json
{"status": "ok", "version": "1.0"}
```

---

## Grading Categories

| Category | Weight | What It Measures |
|----------|--------|------------------|
| Preparation | Equal | Tutor preparation and context awareness |
| Study Plan | Equal | Structure of documented study plan |
| Personalization | Equal | Adaptation to student constraints |
| Strategy | Equal | Teaching methodology documentation |
| Clarity | Equal | Clear next steps for student |

## Rating Thresholds

| Average Score | Rating |
|---------------|--------|
| 8.5 - 10.0 | Strong Session |
| 7.0 - 8.4 | Adequate |
| 5.0 - 6.9 | Needs Improvement |
| Below 5.0 | Review Required |

---

## File Structure

```
course_tutoring_app/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── .env                       # Your config (git-ignored)
├── Dockerfile                 # Container config
├── README.md                  # This file
├── session_1_grading_agent.md # Agent rules/rubric
├── first_session_sop_agent.md # SOP requirements
└── grading_first_session_agent.md # Grading rubric
```

---

## Support

For issues or feature requests, contact the development team.
