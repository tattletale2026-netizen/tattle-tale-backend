import os
import json
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(override=False)

app = Flask(__name__)

# Configure CORS
allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins_str == '*':
    CORS(app)
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()]
    CORS(app, origins=allowed_origins)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

MAIL_TO = os.environ.get('MAIL_TO')

mail = Mail(app)

def get_all_data():
    """Helper to get data from either JSON or Form-data, supporting lists."""
    data = {}
    if request.is_json:
        data = request.get_json() or {}
    else:
        # For form-data, we need to handle multiple values for checkboxes
        for key in request.form.keys():
            values = request.form.getlist(key)
            if len(values) > 1:
                data[key] = values
            else:
                data[key] = values[0]
    return data

@app.route('/', methods=['GET'])
def index():
    return "Tattle Tale backend is running"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/booking', methods=['POST'])
def booking():
    print("[Booking] Received request")
    data = get_all_data()
    
    # Log keys only for privacy
    print(f"[Booking] Payload keys: {list(data.keys())}")
    
    # Support multiple field names for email
    email = (data.get('email') or data.get('user_email') or 
             data.get('Email') or data.get('your_email') or '').strip()
    
    print(f"[Booking] User email detected: {'yes' if email else 'no'}")
    
    if not email:
        print("[Booking Error] Email address is required")
        return jsonify({"success": False, "message": "Email address is required"}), 400

    # Support multiple field names for name
    name = (data.get('name') or data.get('first_name') or 
            data.get('firstName') or data.get('full_name') or 
            data.get('First Name') or '').strip()
    
    # If we have first and last name separately
    if not name:
        first = data.get('first_name') or data.get('First Name') or ''
        last = data.get('last_name') or data.get('Last Name') or ''
        name = f"{first} {last}".strip()

    phone = data.get('phone', '')
    message = data.get('message', '')

    admin_body = f"New Booking:\n\n"
    admin_body += f"Name: {name}\n"
    admin_body += f"Email: {email}\n"
    admin_body += f"Phone: {phone}\n"
    if message:
        admin_body += f"Message: {message}\n"
    
    admin_body += "\n--- All Submitted Fields ---\n"
    for key, val in data.items():
        admin_body += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            # Admin Email
            admin_msg = Message(subject='New Workshop Booking', recipients=[MAIL_TO])
            admin_msg.body = admin_body
            mail.send(admin_msg)
            print("[Booking] Admin email sent")
            
            # User Confirmation
            user_msg = Message(subject='Your Seat is Confirmed', recipients=[email])
            user_msg.body = f"Dear {name or 'Customer'},\n\nThank you for booking. Your seat is confirmed."
            mail.send(user_msg)
            print("[Booking] User confirmation sent")

        return jsonify({"success": True, "message": "Booking submitted successfully"})
    except Exception as e:
        import traceback
        print(f"[Booking Error] {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/survey', methods=['POST'])
def survey():
    print("[Survey] Received request")
    data = get_all_data()
    print(f"[Survey] Payload keys: {list(data.keys())}")
    
    body_content = "New Community Survey Response\n\n"
    for key, val in data.items():
        if isinstance(val, list):
            body_content += f"{key}: {', '.join(str(v) for v in val)}\n"
        else:
            body_content += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject='New Community Survey Response', recipients=[MAIL_TO])
            msg.body = body_content
            mail.send(msg)
            print("[Survey] Admin email sent")
        return jsonify({"success": True, "message": "Survey submitted successfully"})
    except Exception as e:
        import traceback
        print(f"[Survey Error] {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/api/feedback', methods=['POST'])
def feedback():
    # Feedback route remains mostly unchanged as requested, but uses improved get_all_data
    print("[Feedback] Received request")
    data = get_all_data()
    
    body_content = "New Feedback:\n\n"
    for key, val in data.items():
        body_content += f"{key}: {val}\n"

    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject='New Homepage Feedback', recipients=[MAIL_TO])
            msg.body = body_content
            email = data.get('email')
            if email:
                msg.reply_to = email
            mail.send(msg)
            print("[Feedback] Admin email sent")
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
    except Exception as e:
        print(f"[Feedback Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/api/contact', methods=['POST'])
def contact():
    print("[Contact] Received request")
    data = get_all_data()
    
    name = data.get('name', '')
    email = data.get('email', '')
    message = data.get('message', '')

    body_content = f"New Contact Submission:\n\nName: {name}\nEmail: {email}\nMessage: {message}\n"
    
    try:
        if app.config['MAIL_USERNAME'] and MAIL_TO:
            msg = Message(subject=f"New Contact Form Submission from {name}", recipients=[MAIL_TO])
            msg.body = body_content
            if email:
                msg.reply_to = email
            mail.send(msg)
            print("[Contact] Admin email sent")
        return jsonify({"success": True, "message": "Contact submitted successfully"})
    except Exception as e:
        print(f"[Contact Error] {repr(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
