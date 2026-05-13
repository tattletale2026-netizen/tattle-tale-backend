import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(override=False)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Background email thread pool — fire-and-forget, never blocks the response
# ---------------------------------------------------------------------------
executor = ThreadPoolExecutor(max_workers=2)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins_str == '*':
    CORS(app)
else:
    allowed_origins = [o.strip() for o in allowed_origins_str.split(',') if o.strip()]
    CORS(app, origins=allowed_origins)

# ---------------------------------------------------------------------------
# Flask-Mail configuration
# ---------------------------------------------------------------------------
app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']        = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() == 'true'
app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Timeout so a slow SMTP connection doesn't hang forever (seconds)
app.config['MAIL_TIMEOUT']        = 10

MAIL_TO = os.environ.get('MAIL_TO')

mail = Mail(app)

# ---------------------------------------------------------------------------
# Startup config log (never prints secrets)
# ---------------------------------------------------------------------------
print(f"[Config] MAIL_USERNAME loaded: {'yes' if app.config['MAIL_USERNAME'] else 'no'}")
print(f"[Config] MAIL_TO loaded: {'yes' if MAIL_TO else 'no'}")
print(f"[Config] MAIL_SERVER loaded: {app.config['MAIL_SERVER']}")
print(f"[Config] ALLOWED_ORIGINS: {allowed_origins_str}")
sys.stdout.flush()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_all_data():
    """Normalise JSON or form-data into a plain dict, keeping lists for
    multi-value fields (checkboxes)."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    data = {}
    for key in request.form.keys():
        values = request.form.getlist(key)
        data[key] = values if len(values) > 1 else values[0]
    return data


def _send_mail_background(app_ctx, messages):
    """Run inside the thread-pool.  `messages` is a list of Message objects."""
    with app_ctx:
        for msg in messages:
            try:
                mail.send(msg)
                print(f"[Email] Sent: {msg.subject}  ->  {msg.recipients}")
            except Exception:
                print(f"[Email Error] Failed: {msg.subject}  ->  {msg.recipients}")
                traceback.print_exc()
            sys.stdout.flush()


def send_emails_in_background(*messages):
    """Submit email(s) to the thread pool — returns immediately."""
    if not app.config['MAIL_USERNAME'] or not MAIL_TO:
        print("[Email] Skipped — MAIL_USERNAME or MAIL_TO not set")
        return
    # We need a copy of the app context for the background thread
    ctx = app.app_context()
    executor.submit(_send_mail_background, ctx, list(messages))

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    return "Tattle Tale backend is running"


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


# ---- BOOKING ---------------------------------------------------------------

@app.route('/booking', methods=['POST'])
def booking():
    try:
        print("[Booking] Received request")
        data = get_all_data()
        print(f"[Booking] Payload keys: {list(data.keys())}")

        # Flexible email detection
        email = (data.get('email') or data.get('user_email') or
                 data.get('Email') or data.get('your_email') or '').strip()

        print(f"[Booking] User email detected: {'yes' if email else 'no'}")

        if not email:
            return jsonify({"success": False,
                            "message": "Email address is required"}), 400

        # Flexible name detection
        name = (data.get('name') or '').strip()
        if not name:
            first = (data.get('first_name') or data.get('firstName') or
                     data.get('First Name') or '')
            last  = (data.get('last_name') or data.get('Last Name') or '')
            name = f"{first} {last}".strip()

        phone   = data.get('phone', '')
        message = data.get('message', '')

        # Build admin email body from ALL fields
        admin_body  = "New Booking:\n\n"
        admin_body += f"Name: {name}\nEmail: {email}\nPhone: {phone}\n"
        if message:
            admin_body += f"Message: {message}\n"
        admin_body += "\n--- All Submitted Fields ---\n"
        for k, v in data.items():
            admin_body += f"{k}: {v}\n"

        admin_msg = Message(subject='New Workshop Booking',
                            recipients=[MAIL_TO])
        admin_msg.body = admin_body

        user_msg = Message(subject='Your Seat is Confirmed',
                           recipients=[email])
        user_msg.body = (f"Dear {name or 'Customer'},\n\n"
                         "Thank you for booking. Your seat is confirmed.\n"
                         "Our team will contact you soon with additional details.\n\n"
                         "Warmly,\nThe Tatle tale Team")

        # Fire-and-forget — response goes back NOW
        send_emails_in_background(admin_msg, user_msg)
        print("[Booking] Accepted request, sending emails in background")

        return jsonify({"success": True,
                        "message": "Booking submitted successfully. Confirmation email is being sent."})

    except Exception:
        traceback.print_exc()
        return jsonify({"success": False,
                        "message": "Internal server error"}), 500


# ---- SURVEY ----------------------------------------------------------------

@app.route('/survey', methods=['POST'])
def survey():
    try:
        print("[Survey] Received request")
        data = get_all_data()
        print(f"[Survey] Payload keys: {list(data.keys())}")

        body = "New Community Survey Response\n\n"
        for k, v in data.items():
            if isinstance(v, list):
                body += f"{k}: {', '.join(str(i) for i in v)}\n"
            else:
                body += f"{k}: {v}\n"

        msg = Message(subject='New Community Survey Response',
                      recipients=[MAIL_TO])
        msg.body = body

        send_emails_in_background(msg)
        print("[Survey] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Survey submitted successfully."})

    except Exception:
        traceback.print_exc()
        return jsonify({"success": False,
                        "message": "Internal server error"}), 500


# ---- FEEDBACK --------------------------------------------------------------

@app.route('/api/feedback', methods=['POST'])
def feedback():
    try:
        print("[Feedback] Received request")
        data = get_all_data()

        body = "New Feedback:\n\n"
        for k, v in data.items():
            body += f"{k}: {v}\n"

        msg = Message(subject='New Homepage Feedback',
                      recipients=[MAIL_TO])
        msg.body = body
        email = data.get('email')
        if email:
            msg.reply_to = email

        send_emails_in_background(msg)
        print("[Feedback] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Feedback sent successfully."})

    except Exception:
        traceback.print_exc()
        return jsonify({"success": False,
                        "message": "Internal server error"}), 500


# ---- CONTACT ---------------------------------------------------------------

@app.route('/api/contact', methods=['POST'])
def contact():
    try:
        print("[Contact] Received request")
        data = get_all_data()

        name    = data.get('name', '')
        email   = data.get('email', '')
        message = data.get('message', '')

        body = f"New Contact Submission:\n\nName: {name}\nEmail: {email}\nMessage: {message}\n"

        msg = Message(subject=f"New Contact Form Submission from {name}",
                      recipients=[MAIL_TO])
        msg.body = body
        if email:
            msg.reply_to = email

        send_emails_in_background(msg)
        print("[Contact] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Message sent successfully."})

    except Exception:
        traceback.print_exc()
        return jsonify({"success": False,
                        "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
