# Tattle Tale — Flask Backend

Production email-sending backend for the Tattle Tale website.  
Receives form submissions (booking, survey, feedback, contact) and sends emails via Gmail SMTP.

---

## Architecture

| File               | Purpose                                    |
|--------------------|--------------------------------------------|
| `app.py`           | Flask application with all routes           |
| `requirements.txt` | Python dependencies                         |
| `.env.example`     | Template for local environment variables    |
| `.gitignore`       | Prevents secrets & cache from being committed |
| `README.md`        | This file                                   |

---

## Routes

| Method | Path             | Purpose                              |
|--------|------------------|--------------------------------------|
| GET    | `/`              | Heartbeat — plain text               |
| GET    | `/health`        | Health check — `{"status": "ok"}`    |
| GET    | `/debug-config`  | Shows env var status (yes/no only)   |
| GET    | `/debug-smtp`    | Tests SMTP socket connectivity       |
| GET    | `/debug-mail`    | Sends a real test email to MAIL_TO   |
| POST   | `/booking`       | Workshop booking form                |
| POST   | `/survey`        | Community survey form                |
| POST   | `/api/feedback`  | Feedback form                        |
| POST   | `/api/contact`   | Contact form                         |

---

## Render Deployment

### Build Command

```
pip install -r requirements.txt
```

### Start Command

```
gunicorn app:app --workers 1 --threads 8 --timeout 120
```

### Health Check Path

```
/health
```

### Render Environment Variables

Add these in the Render dashboard under **Environment → Environment Variables**:

| Variable             | Value                        |
|----------------------|------------------------------|
| `MAIL_SERVER`        | `smtp.gmail.com`             |
| `MAIL_PORT`          | `587`                        |
| `MAIL_USE_TLS`       | `True`                       |
| `MAIL_SSL_PORT`      | `465`                        |
| `MAIL_USERNAME`      | your Gmail address           |
| `MAIL_PASSWORD`      | your Gmail **App Password**  |
| `MAIL_DEFAULT_SENDER`| your Gmail address           |
| `MAIL_TO`            | admin receiving email        |
| `ALLOWED_ORIGINS`    | `*` or comma-separated URLs  |
| `VENUE_LINK`         | Google Maps / venue URL      |

> **Important:** `MAIL_PASSWORD` must be a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your normal Gmail password.

---

## Local Development

### 1. Create your `.env`

```bash
cp .env.example .env
# Edit .env with your real credentials
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
python app.py
```

Server starts at `http://127.0.0.1:5000`

### 4. Test locally

Open in browser:

- http://127.0.0.1:5000/ — heartbeat
- http://127.0.0.1:5000/health — health check
- http://127.0.0.1:5000/debug-config — verify env vars loaded
- http://127.0.0.1:5000/debug-smtp — verify SMTP connectivity
- http://127.0.0.1:5000/debug-mail — send a real test email

Test POST routes with curl:

```bash
# Feedback
curl -X POST http://127.0.0.1:5000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@test.com","message":"Hello"}'

# Survey
curl -X POST http://127.0.0.1:5000/survey \
  -H "Content-Type: application/json" \
  -d '{"age_group":"25-34","interest":"Art","feedback":"Great!"}'

# Booking
curl -X POST http://127.0.0.1:5000/booking \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Doe","email":"jane@test.com","phone":"07123456789","workshop":"Workshop 1","seats":"2"}'

# Contact
curl -X POST http://127.0.0.1:5000/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@test.com","message":"Hello"}'
```

---

## Testing on Render

After deploying, test these URLs (replace with your domain):

1. `https://your-backend.onrender.com/` — should show heartbeat text
2. `https://your-backend.onrender.com/health` — should return `{"status":"ok"}`
3. `https://your-backend.onrender.com/debug-config` — all values should say `yes`
4. `https://your-backend.onrender.com/debug-smtp` — both ports should say `ok`
5. `https://your-backend.onrender.com/debug-mail` — should send test email
6. Test your frontend forms point to the Render backend URL

---

## Troubleshooting

| Problem                        | Check                                               |
|--------------------------------|-----------------------------------------------------|
| `/debug-config` shows `no`     | Environment variable missing in Render dashboard     |
| `/debug-smtp` shows error      | Firewall or network issue on host                    |
| `/debug-mail` fails            | Check MAIL_USERNAME and MAIL_PASSWORD (App Password) |
| CORS errors in browser         | Set `ALLOWED_ORIGINS` to `*` or your frontend URL    |
| Emails not arriving            | Check spam folder; verify App Password is correct    |
