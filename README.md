# Tattle Tale — Production Backend

Node.js Express API using Prisma ORM and Supabase PostgreSQL.

---

## 🚀 Quick Start (Local)

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase and Resend keys
   ```

3. **Initialize Database**
   ```bash
   npx prisma generate
   npx prisma migrate dev --name init
   ```

4. **Run Server**
   ```bash
   npm run dev
   ```

---

## 📦 Production Deployment (Render)

### Build Command
```bash
npm install && npx prisma generate && npx prisma migrate deploy
```

### Start Command
```bash
npm start
```

### Required Environment Variables
| Key | Description |
|---|---|
| `DATABASE_URL` | Supabase connection string (transaction mode) |
| `DIRECT_URL` | Supabase connection string (session mode) |
| `RESEND_API_KEY` | Your Resend API key |
| `MAIL_FROM` | Verified sender in Resend |
| `MAIL_TO` | Admin email address |
| `ADMIN_API_KEY` | Secret key for admin routes |
| `ALLOWED_ORIGINS` | Comma-separated frontend URLs |

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
- `GET /api/admin/bookings`
- `GET /api/admin/surveys`
- `GET /api/admin/feedback`
- `GET /api/admin/contact-messages`
- `GET /api/admin/dashboard-summary`

---

## 🗄️ Database Setup (Supabase)

1. Create a project in [Supabase](https://supabase.com).
2. Go to **Project Settings > Database**.
3. Copy the **Connection string** (URI).
4. For `DATABASE_URL`, use the string with `port 6543` (Transaction mode).
5. For `DIRECT_URL`, use the string with `port 5432` (Session mode).
