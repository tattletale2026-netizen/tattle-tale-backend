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

load_dotenv(override=False)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Background email thread pool
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
# Mail config from environment (used by smtplib directly)
# ---------------------------------------------------------------------------
MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS        = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() == 'true'
MAIL_USERNAME       = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
MAIL_TO             = os.environ.get('MAIL_TO', '')

# ---------------------------------------------------------------------------
# Startup config log (never prints secrets)
# ---------------------------------------------------------------------------
print(f"[Config] MAIL_SERVER: {MAIL_SERVER}")
print(f"[Config] MAIL_PORT: {MAIL_PORT}")
print(f"[Config] MAIL_USE_TLS: {MAIL_USE_TLS}")
print(f"[Config] MAIL_USERNAME loaded: {'yes' if MAIL_USERNAME else 'no'}")
print(f"[Config] MAIL_PASSWORD loaded: {'yes' if MAIL_PASSWORD else 'no'}")
print(f"[Config] MAIL_DEFAULT_SENDER loaded: {'yes' if MAIL_DEFAULT_SENDER else 'no'}")
print(f"[Config] MAIL_TO loaded: {'yes' if MAIL_TO else 'no'}")
print(f"[Config] ALLOWED_ORIGINS: {allowed_origins_str}")
sys.stdout.flush()

# ---------------------------------------------------------------------------
# Direct smtplib email sender (thread-safe, no Flask context needed)
# ---------------------------------------------------------------------------

def connect_smtp_ipv4(host, port, timeout=15):
    """Resolve host to IPv4 only and connect. Fixes Render IPv6 unreachable."""
    addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    last_error = None

    for family, socktype, proto, canonname, sockaddr in addresses:
        ip = sockaddr[0]
        try:
            print(f"[SMTP] Trying IPv4 {ip}:{port} for {host}")
            sys.stdout.flush()
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(ip, port)
            # Restore hostname so TLS/SNI certificate validation works
            smtp._host = host
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            print(f"[SMTP] Connected using IPv4 {ip}")
            sys.stdout.flush()
            return smtp
        except Exception as e:
            last_error = e
            print(f"[SMTP] IPv4 connection failed for {ip}: {e}")
            sys.stdout.flush()

    raise last_error or RuntimeError("No IPv4 SMTP address available")


def _smtp_send(recipient, subject, body):
    """Send one email via smtplib over IPv4. Returns True on success."""
    msg = MIMEMultipart()
    msg['From']    = MAIL_DEFAULT_SENDER
    msg['To']      = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    print(f"[Email Worker] Connecting to {MAIL_SERVER}:{MAIL_PORT} ...")
    sys.stdout.flush()

    server = connect_smtp_ipv4(MAIL_SERVER, MAIL_PORT, timeout=15)
    try:
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("[SMTP] Logged in")
        sys.stdout.flush()
        server.sendmail(MAIL_DEFAULT_SENDER, [recipient], msg.as_string())
        print(f"[Email Worker] Sent OK to: {recipient}  subject: {subject}")
        sys.stdout.flush()
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _background_send(emails):
    """Run inside the thread pool.  `emails` is a list of (recipient, subject, body) tuples."""
    print(f"[Email Worker] Started — {len(emails)} email(s) to send")
    sys.stdout.flush()
    for recipient, subject, body in emails:
        try:
            print(f"[Email Worker] Sending to: {recipient}")
            sys.stdout.flush()
            _smtp_send(recipient, subject, body)
        except Exception:
            print(f"[Email Worker Error] Failed sending to {recipient}")
            traceback.print_exc()
            sys.stdout.flush()
    print("[Email Worker] Finished")
    sys.stdout.flush()


def _future_done_callback(future):
    """Catch any exception that the thread pool might swallow silently."""
    exc = future.exception()
    if exc:
        print(f"[Email Worker Error] Unhandled exception in background thread: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        sys.stdout.flush()


def send_emails_in_background(emails):
    """Submit email(s) to the thread pool — returns immediately.
    `emails` is a list of (recipient, subject, body) tuples.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print("[Email] Skipped — MAIL_USERNAME or MAIL_PASSWORD not set")
        sys.stdout.flush()
        return
    if not emails:
        return
    future = executor.submit(_background_send, emails)
    future.add_done_callback(_future_done_callback)


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    return "Tattle Tale backend is running"


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


# ---- DEBUG (temporary) -----------------------------------------------------

@app.route('/debug-mail', methods=['GET'])
def debug_mail():
    """Send one test email synchronously so we can see the exact error."""
    if not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_TO:
        return jsonify({"success": False,
                        "message": "Missing MAIL_USERNAME, MAIL_PASSWORD, or MAIL_TO"}), 500
    try:
        _smtp_send(MAIL_TO, 'Tattle Tale Backend — Test Email',
                   'If you received this, your email config is working correctly.')
        return jsonify({"success": True, "message": "Test email sent"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


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

        user_body = (f"Dear {name or 'Customer'},\n\n"
                     "Thank you for booking. Your seat is confirmed.\n"
                     "Our team will contact you soon with additional details.\n\n"
                     "Warmly,\nThe Tatle tale Team")

        # Queue emails for background sending
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

        emails = [(MAIL_TO, 'New Community Survey Response', body)]
        send_emails_in_background(emails)
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

        emails = [(MAIL_TO, 'New Homepage Feedback', body)]
        send_emails_in_background(emails)
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

        emails = [(MAIL_TO, f"New Contact Form Submission from {name}", body)]
        send_emails_in_background(emails)
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
