# Tattle Tale Backend

This is the Flask backend for Tattle Tale, designed to be deployed on Render.

## Deployment on Render
1. Connect this repository to a new Web Service on Render.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app --workers 1 --threads 8 --timeout 120`
4. Set the environment variables as described in `.env.example`. Make sure `MAIL_PASSWORD` is a Gmail App Password.
