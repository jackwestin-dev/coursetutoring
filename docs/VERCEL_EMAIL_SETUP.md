# Receiving emails from the Session Grader on Vercel

To get the **management email** (and the 3-day director digest) when the app runs on Vercel, set these in the project’s **Environment Variables**:

## Required for sending mail

| Variable | Example | Notes |
|----------|---------|--------|
| `SMTP_SERVER` | `smtp.office365.com` or `smtp.gmail.com` | **Hostname only** — not an email address. Use your provider’s SMTP server. |
| `SMTP_PORT` | `587` | Optional in code (defaults to 587). Set if your provider uses a different port. |
| `FROM_EMAIL` | `anastasia@jackwestin.com` | “From” address. If you don’t set `SMTP_USER`, this is also used as the SMTP login. |
| `SMTP_USER` | *(optional)* | SMTP login; if unset, `FROM_EMAIL` is used. |
| `SMTP_PASSWORD` | *(app password)* | Password or app password for `SMTP_USER` / `FROM_EMAIL`. |

## Who receives the emails

| Variable | Description |
|----------|-------------|
| `DIRECTOR_EMAILS` | Comma-separated list, e.g. `anastasia@jackwestin.com,molly@jackwestin.com,carl@jackwestin.com,adam@jackwestin.com` |
| or `DIRECTOR_EMAIL` | Single address used if `DIRECTOR_EMAILS` is not set (e.g. `anastasia@jackwestin.com`) |

## Checklist

1. In Vercel: **Project → Settings → Environment Variables**
2. Add each variable above for **Production** (and Preview if you want it there too).
3. **Redeploy** after changing env vars (or trigger a new deployment) so the serverless functions get the new values.
4. For **Gmail**: use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.
5. If you still don’t receive mail: open your deployment URL + `/api/send-email` in the browser (GET) to see if SMTP is configured. Then check Vercel **Project → Logs** for `/api/send-email` errors; the app also shows the error under "Email not sent" after grading.

No need to “add emails to” SMTP itself — SMTP is the **sending** account. The **recipients** are determined by `DIRECTOR_EMAILS` (or `DIRECTOR_EMAIL`) in the app.
