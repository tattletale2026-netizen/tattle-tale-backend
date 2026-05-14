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
            "from": os.environ.get('MAIL_FROM', 'noreply@tatletale.com'),
            "to": [to],
            "subject": subject,
            "html": html,
        }
        email_response = resend.Emails.send(params)
        print(f"[Resend Success] Email sent to {to}. ID: {getattr(email_response, 'id', 'unknown')}")
        return True, email_response
    except Exception as e:
        # resend-python exceptions usually contain the error details in the string representation
        error_msg = str(e)
        print(f"[Resend Error] Failed to send to {to}: {error_msg}")
        
        # Additional logic to highlight 403 specifically if it appears in the message
        if "403" in error_msg or "Forbidden" in error_msg:
            print("[Resend Error] 403 Forbidden detected. This usually means the sender domain is not verified or you are trying to send to an external email using a trial/onboarding address.")
            
        return False, error_msg

    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;border:1px solid #eee;padding:20px;border-radius:10px;">
        <h2 style="color:#174f63;">{title}</h2>
        <table style="width:100%;border-collapse:collapse;">{rows}</table>
        <p style="font-size:12px;color:#666;margin-top:20px;">Submitted at: {datetime.utcnow().isoformat()}</p>
    </div>
    """

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

def format_user_booking_html(name, data, venue_link):
    rows = ""
    # Map friendly names for the user table
    fields = {
        "Workshop": data.get('workshop', 'Tattle Tale Workshop'),
        "Seats": data.get('seats', '1'),
        "Date": data.get('date', 'TBD'),
        "Time": data.get('time', 'TBD'),
        "Name": name,
        "Email": data.get('email') or data.get('user_email') or '',
        "Phone": data.get('phone') or data.get('mobile') or 'N/A'
    }
    
    for k, v in fields.items():
        if v:
            rows += f"<tr><td style='padding:10px 0;border-bottom:1px solid #f0f0f0;color:#555;'><strong>{k}</strong></td><td style='padding:10px 0;border-bottom:1px solid #f0f0f0;color:#333;text-align:right;'>{v}</td></tr>"

    venue_section = ""
    if venue_link:
        venue_section = f"""
        <div style="margin-top:30px;padding:20px;background-color:#f9fbfb;border-radius:8px;text-align:center;">
            <p style="margin-bottom:15px;color:#555;"><strong>Venue</strong></p>
            <a href="{venue_link}" style="background-color:#174f63;color:#ffffff;padding:12px 25px;text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">View Workshop Venue</a>
        </div>
        """
    else:
        venue_section = """
        <div style="margin-top:30px;padding:20px;background-color:#f9fbfb;border-radius:8px;text-align:center;">
            <p style="margin-bottom:0;color:#777;">Venue details will be shared by our team soon.</p>
        </div>
        """

    return f"""
    <div style="font-family:'Helvetica Neue', Helvetica, Arial, sans-serif;max-width:600px;margin:auto;background-color:#f4f7f7;padding:40px 20px;">
        <div style="background-color:#ffffff;padding:40px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.05);">
            <div style="text-align:center;margin-bottom:30px;">
                <h1 style="color:#174f63;margin-bottom:10px;font-size:28px;">Tattle Tale</h1>
                <div style="display:inline-block;background-color:#e8f5e9;color:#2e7d32;padding:6px 15px;border-radius:20px;font-size:14px;font-weight:bold;">
                    ✓ Booking Confirmed
                </div>
            </div>
            
            <h2 style="color:#333;font-size:22px;margin-bottom:20px;">Hello {name},</h2>
            <p style="color:#555;line-height:1.6;font-size:16px;">
                Your seat is confirmed! Thank you for booking a spot with Tattle Tale. We're excited to have you join us.
            </p>
            
            <div style="margin-top:35px;">
                <h3 style="color:#174f63;border-bottom:2px solid #174f63;display:inline-block;padding-bottom:5px;margin-bottom:15px;font-size:18px;">Booking Details</h3>
                <table style="width:100%;border-collapse:collapse;font-size:15px;">
                    {rows}
                </table>
            </div>
            
            {venue_section}
            
            <div style="margin-top:40px;padding-top:20px;border-top:1px solid #eee;text-align:center;">
                <p style="color:#555;font-size:16px;margin-bottom:5px;">See you soon,</p>
                <p style="color:#174f63;font-weight:bold;font-size:18px;margin-top:0;">Tattle Tale Team</p>
            </div>
        </div>
        <div style="text-align:center;margin-top:20px;color:#999;font-size:12px;">
            <p>© {datetime.now().year} Tattle Tale. All rights reserved.</p>
        </div>
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
        email = (
            data.get('email') or 
            data.get('user_email') or 
            data.get('Email') or 
            data.get('your_email') or 
            data.get('Your email address') or 
            ''
        )
        first_name = data.get('first_name') or data.get('firstName') or ''
        last_name = data.get('last_name') or data.get('lastName') or ''
        full_name = data.get('name') or f"{first_name} {last_name}".strip()
        
        if not email:
            print("[Booking Error] No email found in request data")
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
        print(f"[Booking] Saved to database: {new_booking.id}")

        # 2. Send Emails via Resend
        admin_html = format_admin_html("New Workshop Booking", data)
        greeting_name = full_name if full_name else "there"
        
        venue_link = os.environ.get('VENUE_LINK', '')
        user_html = format_user_booking_html(greeting_name, data, venue_link)
        print("[Booking] User confirmation email template prepared")
        print(f"[Booking] Venue link included: {'yes' if venue_link else 'no'}")
        
        # Admin Email
        print("[Booking] Admin email send attempt")
        admin_sent, admin_err = send_resend_email(os.environ.get('MAIL_TO'), "New Workshop Booking - Tattle Tale", admin_html)
        if admin_sent:
            print("[Booking] Admin email sent")
        else:
            print(f"[Booking Email Error] Admin email failed: {admin_err}")

        # User Email
        print(f"[Booking] User confirmation send attempt to: {email}")
        user_sent, user_err = send_resend_email(email, "Your Seat is Confirmed - Tattle Tale", user_html)
        
        if user_sent:
            print("[Booking] User confirmation sent")
            return jsonify({"success": True, "message": "Booking saved and emails sent!", "id": new_booking.id}), 201
        else:
            print(f"[Booking Email Error] User email failed: {user_err}")
            return jsonify({
                "success": True,
                "message": "Booking saved. Admin email sent. User confirmation email failed.",
                "warning": "user_email_failed",
                "id": new_booking.id
            }), 201

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

        # Send Email via Resend
        admin_html = format_admin_html("New Community Survey Response", data)
        print("[Survey] Admin email send attempt")
        sent, err = send_resend_email(os.environ.get('MAIL_TO'), "New Survey Response - Tattle Tale", admin_html)
        if sent:
            print("[Survey] Admin email sent")
        else:
            print(f"[Survey Email Error] Admin email failed: {err}")

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

        # Send Email via Resend
        admin_html = format_admin_html("New Feedback", data)
        print("[Feedback] Admin email send attempt")
        sent, err = send_resend_email(os.environ.get('MAIL_TO'), "New Feedback - Tattle Tale", admin_html)
        if sent:
            print("[Feedback] Admin email sent")
        else:
            print(f"[Feedback Email Error] Admin email failed: {err}")

        return jsonify({"success": True, "message": "Feedback saved!", "id": new_feedback.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/contact", methods=["POST"])
def submit_contact():
    try:
        data = get_request_data()
        new_contact = ContactMessage(
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone'),
            subject=data.get('subject', 'General Inquiry'),
            message=data.get('message'),
            raw_data=data
        )
        db.session.add(new_contact)
        db.session.commit()

        # Send Email via Resend
        admin_html = format_admin_html("New Contact Message", data)
        print("[Contact] Admin email send attempt")
        sent, err = send_resend_email(os.environ.get('MAIL_TO'), "New Contact Message - Tattle Tale", admin_html)
        if sent:
            print("[Contact] Admin email sent")
        else:
            print(f"[Contact Email Error] Admin email failed: {err}")

        return jsonify({"success": True, "message": "Message sent!", "id": new_contact.id}), 201
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
