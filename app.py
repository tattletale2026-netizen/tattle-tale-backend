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

def send_resend_email(to, subject, html, text=None):
    try:
        params = {
            "from": os.environ.get('MAIL_FROM', 'noreply@tatletale.com'),
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            params["text"] = text
            
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

def build_user_booking_confirmation_email(booking, raw_data):
    # Field extraction with fallbacks
    user_name = booking.full_name or "there"
    user_email = booking.email
    phone = booking.phone or "N/A"
    seats = booking.seats or "1"
    
    # Workshop defaults
    default_workshop = "Tattle Tale Talks"
    default_date = "23rd May 2025"
    default_time = "11:00 AM – 12:00 PM"
    
    workshop_title = booking.workshop or default_workshop
    event_date = booking.event_date or default_date
    event_time = booking.event_time or default_time
    
    venue_address = "40A Bank St, Sheffield City Centre, Sheffield S1 2DS"
    venue_link = os.environ.get('VENUE_LINK') or "https://www.google.com/maps/search/?api=1&query=40A%20Bank%20St%2C%20Sheffield%20City%20Centre%2C%20Sheffield%20S1%202DS"
    
    # HTML Template
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #f4f7f7; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f7f7; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px 40px; text-align: center;">
                                <h1 style="color: #174f63; margin: 0; font-size: 32px; letter-spacing: 1px;">Tattle Tale</h1>
                                <p style="color: #666; margin: 5px 0 0 0; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">Your seat is confirmed</p>
                            </td>
                        </tr>

                        <!-- Hero Section -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px; text-align: center;">
                                <div style="display: inline-block; background-color: #e8f5e9; color: #2e7d32; padding: 8px 20px; border-radius: 30px; font-size: 14px; font-weight: bold; margin-bottom: 20px;">
                                    ✓ Seat Confirmed
                                </div>
                                <h2 style="color: #333; margin: 0 0 10px 0; font-size: 26px;">Welcome to Tattle Tale Talks</h2>
                                <p style="color: #555; margin: 0; font-size: 16px;">Chapter 1 · {event_date} · {event_time}</p>
                            </td>
                        </tr>

                        <!-- Intro -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px;">
                                <p style="color: #444; font-size: 16px; line-height: 1.6; margin: 0;">
                                    Hello {user_name},<br><br>
                                    Your seat has been confirmed. Thank you for booking your place with Tattle Tale. We are delighted to welcome you to a warm, reflective workshop filled with stories, stitches, and shared memories.
                                </p>
                            </td>
                        </tr>

                        <!-- Workshop Overview -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px;">
                                <div style="background-color: #f9fbfb; border-radius: 12px; padding: 25px; border: 1px solid #eef2f2;">
                                    <h3 style="color: #174f63; margin: 0 0 5px 0; font-size: 20px;">{workshop_title}</h3>
                                    <p style="color: #174f63; margin: 0 0 15px 0; font-size: 14px; font-style: italic;">A warm-up in stories and stitches</p>
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size: 14px; color: #555;">
                                        <tr><td style="padding: 4px 0;"><strong>Date:</strong> {event_date}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Time:</strong> {event_time}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Duration:</strong> 1 hour session</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Age:</strong> 18+ only</td></tr>
                                    </table>
                                </div>
                            </td>
                        </tr>

                        <!-- Description -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px;">
                                <h3 style="color: #174f63; font-size: 18px; margin: 0 0 10px 0;">About this session</h3>
                                <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0;">
                                    Our journey begins with a conversation. Before the making starts, we gather to share the stories of the fabrics we hold dear. This session is about setting the stage, finding common ground, and preparing our hands and hearts for the creative work ahead.
                                </p>
                            </td>
                        </tr>

                        <!-- Agenda -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px;">
                                <h3 style="color: #174f63; font-size: 18px; margin: 0 0 15px 0;">Workshop Agenda</h3>
                                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size: 14px; color: #555;">
                                    <tr><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">0–10 mins</td><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0; text-align: right;">Welcome & settling in</td></tr>
                                    <tr><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">10–20 mins</td><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0; text-align: right;">Tattle Tale Talks — Story sharing</td></tr>
                                    <tr><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">20–35 mins</td><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0; text-align: right;">Simple stitching alongside stories</td></tr>
                                    <tr><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">35–45 mins</td><td style="padding: 8px 0; border-bottom: 1px solid #f0f0f0; text-align: right;">Reflection & looking ahead</td></tr>
                                    <tr><td style="padding: 8px 0;">Break</td><td style="padding: 8px 0; text-align: right;">10 minute rest</td></tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Booking Details -->
                        <tr>
                            <td style="padding: 0 40px 30px 40px;">
                                <div style="border-top: 2px solid #174f63; padding-top: 20px;">
                                    <h3 style="color: #174f63; font-size: 18px; margin: 0 0 15px 0;">Booking Summary</h3>
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size: 14px; color: #555;">
                                        <tr><td style="padding: 4px 0;"><strong>Name:</strong> {user_name}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Email:</strong> {user_email}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Phone:</strong> {phone}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Workshop:</strong> {workshop_title}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Seats:</strong> {seats}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Date:</strong> {event_date}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Time:</strong> {event_time}</td></tr>
                                        <tr><td style="padding: 4px 0;"><strong>Booking ID:</strong> {booking.id}</td></tr>
                                    </table>
                                </div>
                            </td>
                        </tr>

                        <!-- Venue -->
                        <tr>
                            <td style="padding: 0 40px 40px 40px; text-align: center;">
                                <div style="background-color: #f9fbfb; border-radius: 12px; padding: 30px; border: 1px solid #eef2f2;">
                                    <h3 style="color: #174f63; margin: 0 0 10px 0; font-size: 18px;">Venue Location</h3>
                                    <p style="color: #555; font-size: 15px; margin: 0 0 20px 0; line-height: 1.5;">
                                        40A Bank St,<br>
                                        Sheffield City Centre,<br>
                                        Sheffield S1 2DS
                                    </p>
                                    <a href="{venue_link}" style="background-color: #174f63; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 16px;">View Workshop Venue</a>
                                    <p style="margin-top: 15px; font-size: 12px; color: #999;">
                                        Map Link: <a href="{venue_link}" style="color: #174f63; text-decoration: underline;">{venue_link}</a>
                                    </p>
                                </div>
                            </td>
                        </tr>

                        <!-- Footer Closing -->
                        <tr>
                            <td style="padding: 0 40px 40px 40px; border-top: 1px solid #eee; text-align: center;">
                                <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 30px 0 20px 0;">
                                    Please keep this email as your booking confirmation. Our team will contact you if any further details are required.
                                </p>
                                <p style="color: #174f63; font-weight: bold; font-size: 18px; margin: 0;">Warm regards,</p>
                                <p style="color: #174f63; font-weight: bold; font-size: 18px; margin: 5px 0 0 0;">Tattle Tale Team</p>
                            </td>
                        </tr>
                    </table>

                    <!-- Final Footer -->
                    <table width="600" border="0" cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="padding: 30px 0; text-align: center; color: #999; font-size: 13px;">
                                <p style="margin: 0;">Tattle Tale · Stories, stitches, and shared memories</p>
                                <p style="margin: 5px 0 0 0;">© {datetime.now().year} Tattle Tale</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Plain Text Fallback
    text_body = f"""
    TATTLE TALE - YOUR SEAT IS CONFIRMED
    Welcome to Tattle Tale Talks
    
    Hello {user_name},
    
    Your seat has been confirmed. Thank you for booking your place with Tattle Tale.
    
    WORKSHOP DETAILS:
    Workshop: {workshop_title}
    Subtitle: A warm-up in stories and stitches
    Date: {event_date}
    Time: {event_time}
    Duration: 1 hour session
    Age: 18+ only
    
    DESCRIPTION:
    Our journey begins with a conversation. Before the making starts, we gather to share the stories of the fabrics we hold dear. This session is about setting the stage, finding common ground, and preparing our hands and hearts for the creative work ahead.
    
    AGENDA:
    0–10 mins — Welcome & settling in
    10–20 mins — Tattle Tale Talks — Story sharing
    20–35 mins — Simple stitching alongside stories
    35–45 mins — Reflection & looking ahead
    Break — 10 minute rest
    
    BOOKING SUMMARY:
    Name: {user_name}
    Email: {user_email}
    Phone: {phone}
    Seats: {seats}
    Booking ID: {booking.id}
    
    VENUE LOCATION:
    40A Bank St, Sheffield City Centre, Sheffield S1 2DS
    Map Link: {venue_link}
    
    Warm regards,
    Tattle Tale Team
    
    Tattle Tale · Stories, stitches, and shared memories
    """
    
    return html_body, text_body

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
        
        user_html, user_text = build_user_booking_confirmation_email(new_booking, data)
        print("[Booking] User confirmation email template prepared")
        print("[Booking] Venue address included")
        print(f"[Booking] Venue link included: {'yes' if os.environ.get('VENUE_LINK') else 'no'}")
        
        # Admin Email
        print("[Booking] Admin email send attempt")
        admin_sent, admin_err = send_resend_email(os.environ.get('MAIL_TO'), "New Workshop Booking - Tattle Tale", admin_html)
        if admin_sent:
            print("[Booking] Admin email sent")
        else:
            print(f"[Booking Email Error] Admin email failed: {admin_err}")

        # User Email
        print(f"[Booking] User confirmation send attempt to: {email}")
        user_sent, user_err = send_resend_email(email, "Your Seat is Confirmed - Tattle Tale Talks", user_html, user_text)
        
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
