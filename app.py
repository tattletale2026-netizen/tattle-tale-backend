import os
import sys
import ssl
import socket
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Thread pool for background email sending
# ---------------------------------------------------------------------------
executor = ThreadPoolExecutor(max_workers=2)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins_str == '*':
    CORS(app)
else:
    origins = [o.strip() for o in allowed_origins_str.split(',') if o.strip()]
    CORS(app, origins=origins)

# ---------------------------------------------------------------------------
# Mail config from environment
# ---------------------------------------------------------------------------
MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
MAIL_SSL_PORT       = int(os.environ.get('MAIL_SSL_PORT', 465))
MAIL_USE_TLS        = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() == 'true'
MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '') or MAIL_USERNAME
MAIL_TO             = os.environ.get('MAIL_TO', '')

# ---------------------------------------------------------------------------
# Startup config log (never prints secrets)
# ---------------------------------------------------------------------------
print(f"[Config] MAIL_SERVER loaded: {'yes' if MAIL_SERVER else 'no'}")
print(f"[Config] MAIL_PORT loaded: {'yes' if MAIL_PORT else 'no'}")
print(f"[Config] MAIL_USERNAME loaded: {'yes' if MAIL_USERNAME else 'no'}")
print(f"[Config] MAIL_PASSWORD loaded: {'yes' if MAIL_PASSWORD else 'no'}")
print(f"[Config] MAIL_DEFAULT_SENDER loaded: {'yes' if MAIL_DEFAULT_SENDER else 'no'}")
print(f"[Config] MAIL_TO loaded: {'yes' if MAIL_TO else 'no'}")
sys.stdout.flush()

# ---------------------------------------------------------------------------
# Gmail SMTP sender — tries 587 STARTTLS first, then 465 SSL
# ---------------------------------------------------------------------------

def send_email(recipient, subject, body):
    """Send one email via Gmail SMTP. Tries port 587 first, falls back to 465."""
    msg = MIMEMultipart()
    msg['From']    = MAIL_DEFAULT_SENDER
    msg['To']      = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # --- Attempt 1: SMTP port 587 with STARTTLS ---
    try:
        print(f"[Email] Trying Gmail SMTP 587 -> {recipient}")
        sys.stdout.flush()
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_DEFAULT_SENDER, [recipient], msg.as_string())
        server.quit()
        print(f"[Email] Sent OK to: {recipient} via 587")
        sys.stdout.flush()
        return
    except Exception as e587:
        print(f"[Email] SMTP 587 failed: {e587}")
        sys.stdout.flush()

    # --- Attempt 2: SMTP_SSL port 465 ---
    try:
        print(f"[Email] Trying Gmail SMTP SSL 465 -> {recipient}")
        sys.stdout.flush()
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_SSL_PORT, timeout=20, context=ctx)
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_DEFAULT_SENDER, [recipient], msg.as_string())
        server.quit()
        print(f"[Email] Sent OK to: {recipient} via 465")
        sys.stdout.flush()
        return
    except Exception as e465:
        print(f"[Email] SMTP SSL 465 failed: {e465}")
        traceback.print_exc()
        sys.stdout.flush()
        raise e465


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------

def _background_send(emails):
    """Run inside the thread pool. emails = list of (recipient, subject, body)."""
    print(f"[Email Worker] Started — {len(emails)} email(s) to send")
    sys.stdout.flush()
    for recipient, subject, body in emails:
        try:
            send_email(recipient, subject, body)
        except Exception:
            print(f"[Email Error] Failed sending to {recipient}")
            traceback.print_exc()
            sys.stdout.flush()
    print("[Email Worker] Finished")
    sys.stdout.flush()


def _future_done_callback(future):
    exc = future.exception()
    if exc:
        print(f"[Email Worker Error] Unhandled: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        sys.stdout.flush()


def send_emails_in_background(emails):
    """Submit email(s) to the thread pool — returns immediately."""
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print("[Email] Skipped — MAIL_USERNAME or MAIL_PASSWORD not set")
        sys.stdout.flush()
        return
    if not emails:
        return
    future = executor.submit(_background_send, emails)
    future.add_done_callback(_future_done_callback)


# ---------------------------------------------------------------------------
# Request data helper
# ---------------------------------------------------------------------------

def get_all_data():
    """Normalise JSON or form-data into a plain dict."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    data = {}
    for key in request.form.keys():
        values = request.form.getlist(key)
        data[key] = values if len(values) > 1 else values[0]
    return data


# ===========================================================================
# ROUTES
# ===========================================================================

@app.route('/', methods=['GET'])
def index():
    return "Tattle Tale backend is running"


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


# ---- DEBUG ROUTES ----------------------------------------------------------

@app.route('/debug-config', methods=['GET'])
def debug_config():
    return jsonify({
        "MAIL_SERVER":         "yes" if MAIL_SERVER else "no",
        "MAIL_PORT":           "yes" if MAIL_PORT else "no",
        "MAIL_USERNAME":       "yes" if MAIL_USERNAME else "no",
        "MAIL_PASSWORD":       "yes" if MAIL_PASSWORD else "no",
        "MAIL_DEFAULT_SENDER": "yes" if MAIL_DEFAULT_SENDER else "no",
        "MAIL_TO":             "yes" if MAIL_TO else "no",
    })


@app.route('/debug-smtp', methods=['GET'])
def debug_smtp():
    results = {}

    # Test port 587
    try:
        sock = socket.create_connection((MAIL_SERVER, 587), timeout=10)
        sock.close()
        results["smtp_587"] = "ok"
    except Exception as e:
        results["smtp_587"] = str(e)

    # Test port 465
    try:
        sock = socket.create_connection((MAIL_SERVER, 465), timeout=10)
        sock.close()
        results["smtp_465"] = "ok"
    except Exception as e:
        results["smtp_465"] = str(e)

    return jsonify(results)


@app.route('/debug-mail', methods=['GET'])
def debug_mail():
    if not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_TO:
        return jsonify({"success": False,
                        "message": "Missing MAIL_USERNAME, MAIL_PASSWORD, or MAIL_TO"}), 500
    try:
        send_email(MAIL_TO,
                   'Tattle Tale Backend - Test Email',
                   'If you received this, your Gmail SMTP config is working.')
        return jsonify({"success": True, "message": "Test email sent"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---- BOOKING ---------------------------------------------------------------

@app.route('/booking', methods=['POST'])
def booking():
    try:
        print("[Booking] Received request")
        data = get_all_data()
        print(f"[Booking] Payload keys: {list(data.keys())}")

        # Flexible email
        email = (data.get('email') or data.get('user_email') or
                 data.get('Email') or data.get('your_email') or '').strip()

        print(f"[Booking] User email detected: {'yes' if email else 'no'}")
        if not email:
            return jsonify({"success": False,
                            "message": "Email address is required"}), 400

        # Flexible name
        name = (data.get('name') or '').strip()
        if not name:
            first = (data.get('first_name') or data.get('firstName') or
                     data.get('First Name') or '')
            last  = (data.get('last_name') or data.get('Last Name') or '')
            name = f"{first} {last}".strip()

        phone   = data.get('phone', '')
        message = data.get('message', '')

        admin_body  = "New Booking:\n\n"
        admin_body += f"Name: {name}\nEmail: {email}\nPhone: {phone}\n"
        if message:
            admin_body += f"Message: {message}\n"
        admin_body += "\n--- All Submitted Fields ---\n"
        for k, v in data.items():
            admin_body += f"{k}: {v}\n"

        user_body = (f"Dear {name or 'Customer'},\n\n"
                     "Thank you for booking. Your seat is confirmed.\n"
                     "Our team will contact you soon.\n\n"
                     "Warmly,\nThe Tatle tale Team")

        emails = [
            (MAIL_TO, 'New Workshop Booking', admin_body),
            (email,   'Your Seat is Confirmed', user_body),
        ]
        send_emails_in_background(emails)
        print("[Booking] Accepted request, sending emails in background")

        return jsonify({"success": True,
                        "message": "Booking submitted successfully. Confirmation email is being sent."})
    except Exception:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


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

        emails = [(MAIL_TO, 'New Community Survey Response', body)]
        send_emails_in_background(emails)
        print("[Survey] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Survey submitted successfully."})
    except Exception:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ---- FEEDBACK --------------------------------------------------------------

@app.route('/api/feedback', methods=['POST'])
def feedback():
    try:
        print("[Feedback] Received request")
        data = get_all_data()

        body = "New Feedback:\n\n"
        for k, v in data.items():
            body += f"{k}: {v}\n"

        emails = [(MAIL_TO, 'New Homepage Feedback', body)]
        send_emails_in_background(emails)
        print("[Feedback] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Feedback sent successfully."})
    except Exception:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


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

        emails = [(MAIL_TO, f"New Contact Form Submission from {name}", body)]
        send_emails_in_background(emails)
        print("[Contact] Accepted request, sending email in background")

        return jsonify({"success": True,
                        "message": "Message sent successfully."})
    except Exception:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
