# Supabase table + Vercel env vars (for daily digest)

Do these two things so the app can store session records and send the **daily director digest**.

---

## Part 1: Create the `session_records` table in Supabase

1. Go to **[supabase.com](https://supabase.com)** and sign in. Open the project you connected to GitHub (or create one).

2. In the left sidebar, click **SQL Editor**.

3. Click **New query**.

4. Copy the entire contents of **`supabase-schema.sql`** from this repo (root of the project). It looks like this:

   ```sql
   -- Run this in Supabase SQL Editor to create the session records table.
   create table if not exists public.session_records (
     id uuid primary key default gen_random_uuid(),
     created_at timestamptz default now(),
     tutor_name text,
     tutor_email text,
     student_name text,
     session_date text,
     session_number text,
     course_type text,
     score int,
     rating text,
     report_text text,
     transcript_text text,
     host_data jsonb,
     fathom_notes text
   );
   ```

5. Paste into the SQL Editor and click **Run** (or press Cmd/Ctrl + Enter).

6. You should see a success message. The table **`session_records`** now exists. Graded sessions from the app will be stored here, and the daily digest will read from it.

---

## Part 2: Get your Supabase URL and service key

1. In Supabase, click **Settings** (gear icon in the left sidebar).

2. Click **API** in the left menu.

3. You’ll see:
   - **Project URL** — e.g. `https://abcdefghijk.supabase.co`. This is your **SUPABASE_URL**.
   - **Project API keys**:
     - **anon public** — do **not** use for the app.
     - **service_role** — click **Reveal** and copy this. This is your **SUPABASE_SERVICE_KEY**.  
     Keep it secret; it bypasses Row Level Security.

---

## Part 3: Add the variables in Vercel

1. Go to **[vercel.com](https://vercel.com)** → your **project** (Session Grader app).

2. Click **Settings** → **Environment Variables**.

3. Add two variables:

   | Name | Value | Environment |
   |------|--------|-------------|
   | **SUPABASE_URL** | Your Project URL from Part 2 (e.g. `https://abcdefghijk.supabase.co`) | Production (and Preview if you use it) |
   | **SUPABASE_SERVICE_KEY** | Your **service_role** key from Part 2 | Production (and Preview if you use it) |

4. Click **Save** for each.

5. **Redeploy** so the new env vars are used: **Deployments** → **⋯** on the latest deployment → **Redeploy**.

---

## Check that it works

- **Table:** In Supabase, **Table Editor** → you should see **`session_records`**.
- **App:** Grade a session in the app; a row should appear in **`session_records`**.
- **Daily digest:** Once cron runs (or you call `GET /api/director-digest`), directors get the daily email using data from this table.

The **.env.example** in the repo already has a comment that Supabase is used for “session records; daily director digest” — no change needed there.
