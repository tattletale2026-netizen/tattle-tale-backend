# Tattle Tale — Production Backend (Flask)

Python Flask API using SQLAlchemy ORM and Supabase PostgreSQL.

---

## 🚀 Quick Start (Local)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase and Resend keys
   ```

3. **Initialize Database**
   The application will automatically create tables in Supabase on startup if they don't exist.

4. **Run Server**
   ```bash
   python app.py
   ```

---

## 📦 Production Deployment (Render)

### Start Command
```bash
gunicorn app:app
```

### Required Environment Variables
| Key | Description |
|---|---|
| `DATABASE_URL` | Supabase connection string |
| `RESEND_API_KEY` | Your Resend API key |
| `MAIL_FROM` | Verified sender in Resend (e.g., noreply@yourdomain.com) |
| `MAIL_TO` | Admin email address |
| `ADMIN_API_KEY` | Secret key for admin routes |
| `ALLOWED_ORIGINS` | Comma-separated frontend URLs (or * for all) |
| `VENUE_LINK` | Link to the venue (used in booking emails) |

---

## 🛠️ API Documentation

### Public Endpoints
- `GET /` — Heartbeat
- `GET /health` — Health Check
- `POST /api/booking` — Submit Workshop Booking
- `POST /api/survey` — Submit Community Survey
- `POST /api/feedback` — Submit Feedback
- `POST /api/contact` — Submit Contact Message

### Admin Endpoints (Requires `x-admin-api-key` header)
- `GET /api/admin/dashboard-summary` — Get record counts

---

## 📧 Troubleshooting Emails (Resend 403)

If Resend returns a **403 Forbidden** error for user confirmation emails:
1. **Verify your domain**: In the Resend dashboard, go to the "Domains" section and verify your sending domain (e.g., `yourdomain.com`).
2. **Set MAIL_FROM**: Once verified, set the `MAIL_FROM` environment variable to a valid address on that domain (e.g., `noreply@yourdomain.com`).
3. **External Recipients**: Resend's trial/onboarding address (`onboarding@resend.dev`) can usually only send to the email address used to sign up for Resend. To send to external customers, a verified domain is required.

---

## 🗄️ Database Setup (Supabase)

1. Create a project in [Supabase](https://supabase.com).
2. Go to **Project Settings > Database**.
3. Copy the **Connection string** (URI).
4. Use this string for the `DATABASE_URL` environment variable.
