"""
Tattle Tale — Production Flask Backend (Optimized)
==================================================
High-performance email backend. No disk usage, background sending,
and Gmail SMTP fallback logic.
"""

import os
import sys
import ssl
import socket
import smtplib
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env
load_dotenv()

app = Flask(__name__)

# Background worker (max 2 threads to respect Gmail limits)
executor = ThreadPoolExecutor(max_workers=2)

# CORS configuration
allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*").strip()
if allowed_origins_raw == "*":
    CORS(app, resources={r"/*": {"origins": "*"}})
else:
    origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
    CORS(app, resources={r"/*": {"origins": origins}})

# Configuration
MAIL_SERVER         = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT           = int(os.environ.get("MAIL_PORT", 587))
MAIL_SSL_PORT       = int(os.environ.get("MAIL_SSL_PORT", 465))
MAIL_USERNAME       = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "") or MAIL_USERNAME
MAIL_TO             = os.environ.get("MAIL_TO", "")
VENUE_LINK          = os.environ.get("VENUE_LINK", "https://maps.app.goo.gl/jm2akVWdZtZcy5XW7")

print(f"[Config] Backend Ready. Origins: {allowed_origins_raw}")
sys.stdout.flush()

# ═══════════════════════════════════════════════════════════════════════════
# EMAIL ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def send_email(recipient, subject, body, html_body=None):
    """Sends email with Port 587 -> 465 fallback."""
    if html_body:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAIL_DEFAULT_SENDER
        msg["To"] = recipient
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
    else:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = MAIL_DEFAULT_SENDER
        msg["To"] = recipient

    # Attempt 587
    try:
        print(f"[Email] Trying 587 -> {recipient}")
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20)
        server.starttls(context=ssl.create_default_context())
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[Email] Success via 587")
        return True
    except Exception as e:
        print(f"[Email] 587 Failed: {e}")

    # Fallback 465
    try:
        print(f"[Email] Trying 465 -> {recipient}")
        server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_SSL_PORT, timeout=20)
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[Email] Success via 465")
        return True
    except Exception as e:
        print(f"[Email Error] All ports failed: {e}")
        raise e

def _bg_send(emails):
    for r, s, b, h in emails:
        try:
            send_email(r, s, b, h)
        except:
            traceback.print_exc()

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return "Tattle Tale backend is running", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/debug-config", methods=["GET"])
def debug_config():
    return jsonify({
        "MAIL_USERNAME": "yes" if MAIL_USERNAME else "no",
        "MAIL_PASSWORD": "yes" if MAIL_PASSWORD else "no",
        "MAIL_TO": "yes" if MAIL_TO else "no",
        "ALLOWED_ORIGINS": allowed_origins_raw
    })

@app.route("/booking", methods=["POST"])
def booking():
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        email = (data.get("email") or data.get("user_email") or "").strip()
        name = (data.get("first_name") or data.get("name") or "Customer").strip()
        
        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400

        # Admin body
        admin_body = f"New Booking\n\nName: {name}\nEmail: {email}\nDetails:\n{data}"
        
        # User HTML body (from your working snippet)
        user_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f9fbfb; padding: 40px; border-radius: 8px; border: 1px solid #e2e8e9;">
            <h1 style="color: #174f63; text-align: center;">Tatle tale</h1>
            <p>Dear {name},</p>
            <p>Your seat has been successfully confirmed for <strong>Workshop One</strong>.</p>
            <div style="background-color: #fff; padding: 20px; border-radius: 6px; border-left: 4px solid #2a8a6e;">
                <p><strong>Important:</strong> Strictly 18+ only. Please bring physical photo ID.</p>
            </div>
            <p><strong>Venue:</strong> <a href="{VENUE_LINK}">Workshop Venue</a></p>
            <p>Warmly,<br>The Tatle tale Team</p>
        </div>
        """
        
        emails = [
            (MAIL_TO, "New Workshop Booking", admin_body, None),
            (email, "Your Seat is Confirmed", "Your seat is confirmed.", user_html)
        ]
        executor.submit(_bg_send, emails)
        
        return jsonify({"success": True, "message": "Booking submitted!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.get_json() if request.is_json else request.form.to_dict()
    body = f"New Feedback Received:\n\n{data}"
    executor.submit(_bg_send, [(MAIL_TO, "New Feedback", body, None)])
    return jsonify({"success": True, "message": "Feedback sent!"})

@app.route("/survey", methods=["POST"])
def survey():
    data = request.get_json() if request.is_json else request.form.to_dict()
    body = f"New Survey Response:\n\n{data}"
    executor.submit(_bg_send, [(MAIL_TO, "New Community Survey", body, None)])
    return jsonify({"success": True, "message": "Survey submitted!"})

@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json() if request.is_json else request.form.to_dict()
    body = f"New Contact Message:\n\n{data}"
    executor.submit(_bg_send, [(MAIL_TO, "New Contact Message", body, None)])
    return jsonify({"success": True, "message": "Message sent!"})

@app.route("/debug-smtp", methods=["GET"])
def debug_smtp():
    """Test raw socket connection to Gmail SMTP ports."""
    results = {}
    
    # Test Port 587
    try:
        sock = socket.create_connection(("smtp.gmail.com", 587), timeout=10)
        sock.close()
        results["smtp_587"] = "ok"
    except Exception as e:
        results["smtp_587"] = str(e)

    # Test Port 465
    try:
        sock = socket.create_connection(("smtp.gmail.com", 465), timeout=10)
        sock.close()
        results["smtp_465"] = "ok"
    except Exception as e:
        results["smtp_465"] = str(e)

    return jsonify(results), 200

@app.route("/debug-mail", methods=["GET"])
def debug_mail():
    """Send a real test email to MAIL_TO."""
    if not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_TO:
        return jsonify({"success": False, "message": "Missing mail credentials or MAIL_TO"}), 500
    
    try:
        send_email(
            MAIL_TO,
            "Tattle Tale — Real Test Email",
            f"Test email sent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        return jsonify({"success": True, "message": "Test email sent"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
