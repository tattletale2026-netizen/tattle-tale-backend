import os
import sys
import json
import resend
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Import models
from models import db, Booking, SurveyResponse, Feedback, ContactMessage

# Load environment
load_dotenv()

app = Flask(__name__)

# --- Database Config (Supabase) ---
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is missing. Add it to .env or Render Environment Variables.")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Resend Config ---
resend.api_key = os.getenv("RESEND_API_KEY")

# --- CORS Config ---
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = allowed_origins_raw.split(",")
CORS(app, resources={r"/api/*": {"origins": allowed_origins if "*" not in allowed_origins else "*"}})

# Initialize Database
db.init_app(app)

with app.app_context():
    # This creates the tables in Supabase if they don't exist
    try:
        db.create_all()
        print("[Database] Tables verified/created in Supabase.")
    except Exception as e:
        print(f"[Database Error] Could not connect to Supabase: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def get_request_data():
    if request.is_json:
        return request.get_json() or {}
    return request.form.to_dict()

def send_resend_email(to, subject, html):
    try:
        params = {
            "from": os.environ.get('MAIL_FROM', 'onboarding@resend.dev'),
            "to": [to],
            "subject": subject,
            "html": html,
        }
        email = resend.Emails.send(params)
        return True, email
    except Exception as e:
        print(f"[Resend Error] {e}")
        return False, str(e)

def format_admin_html(title, data):
    rows = ""
    for k, v in data.items():
        rows += f"<tr><td style='padding:8px;border:1px solid #ddd;'><b>{k}</b></td><td style='padding:8px;border:1px solid #ddd;'>{v}</td></tr>"
    
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;border:1px solid #eee;padding:20px;border-radius:10px;">
        <h2 style="color:#174f63;">{title}</h2>
        <table style="width:100%;border-collapse:collapse;">{rows}</table>
        <p style="font-size:12px;color:#666;margin-top:20px;">Submitted at: {datetime.utcnow().isoformat()}</p>
    </div>
    """

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return "Tattle Tale Flask Backend is running", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "database": "connected"}), 200

@app.route("/api/booking", methods=["POST"])
def create_booking():
    try:
        data = get_request_data()
        
        # Detection logic
        email = data.get('email') or data.get('user_email') or data.get('Email') or ''
        first_name = data.get('first_name') or data.get('firstName') or ''
        last_name = data.get('last_name') or data.get('lastName') or ''
        full_name = data.get('name') or f"{first_name} {last_name}".strip()
        
        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        # 1. Save to Supabase
        new_booking = Booking(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=email,
            phone=data.get('phone') or data.get('mobile') or '',
            workshop=data.get('workshop', ''),
            event_date=data.get('date', ''),
            event_time=data.get('time', ''),
            seats=str(data.get('seats', '1')),
            venue_link=os.environ.get('VENUE_LINK', ''),
            message=data.get('message', ''),
            raw_data=data
        )
        db.session.add(new_booking)
        db.session.commit()

        # 2. Send Emails via Resend
        admin_html = format_admin_html("New Workshop Booking", data)
        user_html = f"<h3>Hello {full_name}</h3><p>Your seat is confirmed! Thank you for booking with Tattle Tale.</p>"
        
        send_resend_email(os.environ.get('MAIL_TO'), "New Workshop Booking - Tattle Tale", admin_html)
        send_resend_email(email, "Your Seat is Confirmed - Tattle Tale", user_html)

        return jsonify({"success": True, "message": "Booking saved and emails sent!", "id": new_booking.id}), 201

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/survey", methods=["POST"])
def submit_survey():
    try:
        data = get_request_data()
        new_survey = SurveyResponse(
            email=data.get('email'),
            name=data.get('name'),
            answers=data,
            raw_data=data
        )
        db.session.add(new_survey)
        db.session.commit()

        admin_html = format_admin_html("New Community Survey Response", data)
        send_resend_email(os.environ.get('MAIL_TO'), "New Survey Response - Tattle Tale", admin_html)

        return jsonify({"success": True, "message": "Survey saved!", "id": new_survey.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    try:
        data = get_request_data()
        new_feedback = Feedback(
            name=data.get('name'),
            email=data.get('email'),
            rating=str(data.get('rating', '')),
            message=data.get('message'),
            raw_data=data
        )
        db.session.add(new_feedback)
        db.session.commit()

        admin_html = format_admin_html("New Feedback", data)
        send_resend_email(os.environ.get('MAIL_TO'), "New Feedback - Tattle Tale", admin_html)

        return jsonify({"success": True, "message": "Feedback saved!", "id": new_feedback.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# --- Admin Routes ---
@app.route("/api/admin/dashboard-summary", methods=["GET"])
def admin_summary():
    api_key = request.headers.get('x-admin-api-key')
    if api_key != os.environ.get('ADMIN_API_KEY'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    return jsonify({
        "success": True,
        "counts": {
            "bookings": Booking.query.count(),
            "surveys": SurveyResponse.query.count(),
            "feedback": Feedback.query.count()
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
